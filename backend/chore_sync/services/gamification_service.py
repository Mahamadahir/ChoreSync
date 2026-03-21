"""Gamification services: points, streaks, badges, leaderboard."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from chore_sync.models import (
    Badge, GroupMembership, TaskOccurrence,
    User, UserBadge, UserStats,
)


@dataclass
class GamificationService:
    """Handles points calculation, streak tracking, badge evaluation."""

    # ------------------------------------------------------------------ #
    #  Points
    # ------------------------------------------------------------------ #

    def calculate_points(self, occurrence: TaskOccurrence) -> int:
        """Calculate points earned for completing an occurrence.

        Base = difficulty × 10
        +20% on-time bonus      — completed before deadline
        +20% emergency bonus    — helped out on someone else's emergency
        -10% per snooze used    — each snooze reduces reward
        Minimum 1 point always awarded.
        """
        base = occurrence.template.difficulty * 10
        multiplier = 1.0

        # On-time bonus
        if occurrence.completed_at and occurrence.completed_at < occurrence.deadline:
            multiplier += 0.2

        # Emergency help bonus — actor is the helper, not the original assignee
        if (
            occurrence.reassignment_reason == 'emergency'
            and occurrence.assigned_to_id != occurrence.original_assignee_id
        ):
            multiplier += 0.2

        # Snooze penalty
        multiplier -= 0.1 * (occurrence.snooze_count or 0)

        return max(1, round(base * multiplier))

    # ------------------------------------------------------------------ #
    #  Streaks
    # ------------------------------------------------------------------ #

    def update_streak(self, *, user_id: str, group_id: str) -> None:
        """Update on-time streak for a user after task completion.

        Streak increments if the user completed a task yesterday (consecutive days).
        Resets to 1 if the last completion was earlier than yesterday.
        Same-day completions don't double-increment the streak.
        """
        user = User.objects.get(id=user_id)
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        if user.last_streak_date == yesterday:
            user.on_time_streak_days += 1
        elif user.last_streak_date != today:
            user.on_time_streak_days = 1

        user.longest_on_time_streak_days = max(
            user.longest_on_time_streak_days, user.on_time_streak_days
        )
        user.last_streak_date = today
        user.save(update_fields=[
            'on_time_streak_days', 'longest_on_time_streak_days', 'last_streak_date'
        ])

        stats, _ = UserStats.objects.get_or_create(user_id=user_id, household_id=group_id)
        stats.current_streak_days = user.on_time_streak_days
        stats.longest_streak_days = user.longest_on_time_streak_days
        stats.save(update_fields=['current_streak_days', 'longest_streak_days'])

    # ------------------------------------------------------------------ #
    #  On-time completion rate
    # ------------------------------------------------------------------ #

    def update_on_time_rate(self, *, user_id: str, group_id: str) -> None:
        """Recalculate and persist on_time_completion_rate for a user in a group."""
        total = TaskOccurrence.objects.filter(
            assigned_to_id=user_id,
            template__group_id=group_id,
            status='completed',
        ).count()

        on_time = TaskOccurrence.objects.filter(
            assigned_to_id=user_id,
            template__group_id=group_id,
            status='completed',
            completed_at__lt=F('deadline'),
        ).count()

        stats, _ = UserStats.objects.get_or_create(user_id=user_id, household_id=group_id)
        stats.on_time_completion_rate = round(on_time / total, 4) if total > 0 else 0.0
        stats.save(update_fields=['on_time_completion_rate'])

    # ------------------------------------------------------------------ #
    #  Badge evaluation
    # ------------------------------------------------------------------ #

    def evaluate_badges(self, *, user_id: str, group_id: str) -> list[str]:
        """Check all badge criteria against current UserStats and award new badges.

        Supported criteria keys:
            streak_days           → UserStats.current_streak_days
            tasks_completed       → UserStats.total_tasks_completed
            total_points          → UserStats.total_points
            on_time_rate          → UserStats.on_time_completion_rate (0.0–1.0)
            category_count        → {"category": "cooking", "count": 10}
                                    counts completed occurrences of that category

        Returns list of badge names newly awarded.
        """
        from chore_sync.models import Group

        stats = UserStats.objects.filter(user_id=user_id, household_id=group_id).first()
        if not stats:
            return []

        group = Group.objects.filter(id=group_id).first()
        if not group:
            return []

        FIELD_ALIASES = {
            'streak_days': 'current_streak_days',
            'tasks_completed': 'total_tasks_completed',
            'on_time_rate': 'on_time_completion_rate',
        }

        awarded = []

        for badge in Badge.objects.all():
            if UserBadge.objects.filter(
                user_id=user_id, badge=badge, household_id=group_id
            ).exists():
                continue

            criteria = badge.criteria
            earned = True

            for key, value in criteria.items():
                if key == 'category_count':
                    # value = {"category": "cooking", "count": 10}
                    category = value.get('category')
                    required = value.get('count', 0)
                    actual = TaskOccurrence.objects.filter(
                        assigned_to_id=user_id,
                        template__group_id=group_id,
                        template__category=category,
                        status='completed',
                    ).count()
                    if actual < required:
                        earned = False
                        break
                else:
                    field = FIELD_ALIASES.get(key, key)
                    actual = getattr(stats, field, None)
                    if actual is None or actual < value:
                        earned = False
                        break

            if earned:
                _, created = UserBadge.objects.get_or_create(
                    user_id=user_id, badge=badge, household=group
                )
                if created:
                    from chore_sync.services.notification_service import NotificationService
                    NotificationService().emit_notification(
                        recipient_id=user_id,
                        notification_type='badge_earned',
                        title=f"Badge earned: {badge.name}",
                        content=f"You earned the '{badge.name}' badge! {badge.description}",
                    )
                    awarded.append(badge.name)

        return awarded

    # ------------------------------------------------------------------ #
    #  Leaderboard
    # ------------------------------------------------------------------ #

    def get_leaderboard(self, *, group_id: str, actor_id: str) -> list[dict]:
        """Return ranked leaderboard for a group.

        Validates actor is a group member. Returns list ordered by total_points desc.
        """
        if not GroupMembership.objects.filter(user_id=actor_id, group_id=group_id).exists():
            raise PermissionError("Not a member of this group.")

        stats_qs = (
            UserStats.objects.filter(household_id=group_id)
            .select_related('user')
            .order_by('-total_points')
        )

        return [
            {
                'rank': idx + 1,
                'user_id': str(s.user_id),
                'username': s.user.username,
                'total_points': s.total_points,
                'total_tasks_completed': s.total_tasks_completed,
                'current_streak_days': s.current_streak_days,
                'longest_streak_days': s.longest_streak_days,
                'on_time_completion_rate': s.on_time_completion_rate,
            }
            for idx, s in enumerate(stats_qs)
        ]
