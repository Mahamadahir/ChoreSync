"""Task lifecycle coordination services for ChoreSync."""
from __future__ import annotations

import calendar as cal_module
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from chore_sync.models import (
    Event, GroupMembership, Notification, TaskOccurrence,
    TaskPreference, TaskTemplate, User, UserStats,
)
from chore_sync.services.group_service import GroupOrchestrator


@dataclass
class TaskLifecycleService:
    """Handles task occurrence generation, assignment, and completion."""

    # ------------------------------------------------------------------ #
    #  Recurrence expansion
    # ------------------------------------------------------------------ #

    @staticmethod
    def _expand_dates(template: TaskTemplate, horizon_days: int) -> list:
        """Return all deadline datetimes for template within the horizon window."""
        now = timezone.now()
        horizon = now + timedelta(days=horizon_days)
        start = template.next_due

        if start > horizon:
            return []

        dates = []

        if template.recurring_choice == 'none':
            if start >= now:
                dates.append(start)

        elif template.recurring_choice == 'weekly':
            current = start
            while current <= horizon:
                if current >= now:
                    dates.append(current)
                current += timedelta(weeks=1)

        elif template.recurring_choice == 'monthly':
            current = start
            while current <= horizon:
                if current >= now:
                    dates.append(current)
                month = current.month + 1
                year = current.year
                if month > 12:
                    month, year = 1, year + 1
                max_day = cal_module.monthrange(year, month)[1]
                current = current.replace(year=year, month=month, day=min(current.day, max_day))

        elif template.recurring_choice == 'every_n_days':
            n = template.recur_value or 1
            current = start
            while current <= horizon:
                if current >= now:
                    dates.append(current)
                current += timedelta(days=n)

        elif template.recurring_choice == 'custom':
            day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
            target_days = {day_map[d] for d in (template.days_of_week or [])}
            current = now.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
            while current <= horizon:
                if current >= now and current.weekday() in target_days:
                    dates.append(current)
                current += timedelta(days=1)

        return dates

    # ------------------------------------------------------------------ #
    #  Generate recurring instances
    # ------------------------------------------------------------------ #

    def generate_recurring_instances(self, *, task_template_id: str, horizon_days: int = 7) -> list[TaskOccurrence]:
        """Materialise upcoming TaskOccurrence rows for a template.

        Inputs:
            task_template_id: Active TaskTemplate to expand.
            horizon_days: How many days ahead to project (default 7).
        Output:
            List of newly created (and assigned) TaskOccurrence objects.
        """
        template = TaskTemplate.objects.select_related('group').filter(
            id=task_template_id, active=True
        ).first()
        if template is None:
            raise ValueError("Task template not found.")

        dates = self._expand_dates(template, horizon_days)
        created = []

        for deadline in dates:
            occurrence, new = TaskOccurrence.objects.get_or_create(
                template=template,
                deadline=deadline,
            )
            if new:
                self.assign_occurrence(occurrence)
                created.append(occurrence)

        return created

    # ------------------------------------------------------------------ #
    #  Assignment — 3-stage pipeline
    # ------------------------------------------------------------------ #

    def assign_occurrence(self, occurrence: TaskOccurrence) -> None:
        """Assign a TaskOccurrence using the 3-stage fairness pipeline.

        Stage 1 — Normalised fairness score (0-1) via compute_assignment_matrix.
        Stage 2 — Preference multiplier (prefer ×0.8, neutral ×1.0, avoid ×1.2).
        Stage 3 — Calendar conflict penalty (+0.5, never excluded).
        Winner = user with lowest final score.
        """
        template = occurrence.template
        group = template.group
        deadline = occurrence.deadline

        # Stage 1: fairness scores
        scores: dict[str, float] = GroupOrchestrator().compute_assignment_matrix(
            group_id=str(group.id)
        )

        # Stage 2: preference multiplier
        PREF_WEIGHT = {'prefer': 0.8, 'neutral': 1.0, 'avoid': 1.2}
        preferences = {
            str(p.user_id): p.preference
            for p in TaskPreference.objects.filter(
                task_template=template, user_id__in=scores.keys()
            )
        }
        for uid in scores:
            scores[uid] *= PREF_WEIGHT[preferences.get(uid, 'neutral')]

        # Stage 3: calendar conflict penalty
        for uid in scores:
            has_conflict = Event.objects.filter(
                calendar__user_id=uid,
                calendar__include_in_availability=True,
                blocks_availability=True,
                start__lt=deadline,
                end__gt=deadline,
            ).exists()
            if has_conflict:
                scores[uid] += 0.5

        winner_id = min(scores, key=scores.get)
        winner = User.objects.get(id=winner_id)

        with transaction.atomic():
            occurrence.assigned_to = winner
            occurrence.status = 'pending'
            occurrence.save(update_fields=['assigned_to', 'status'])

            Notification.objects.create(
                title=f"New task assigned: {template.name}",
                type='task_assigned',
                recipient=winner,
                task_occurrence=occurrence,
                content=(
                    f"You have been assigned '{template.name}' "
                    f"due {deadline.strftime('%d %b %Y')}."
                ),
            )

    # ------------------------------------------------------------------ #
    #  Completion toggle
    # ------------------------------------------------------------------ #

    def toggle_occurrence_completed(
        self, *, occurrence_id: str, completed: bool, actor_id: str
    ) -> TaskOccurrence:
        """Mark an occurrence completed or reopen it.

        Inputs:
            occurrence_id: Target TaskOccurrence.
            completed: True to complete, False to reopen.
            actor_id: User performing the action (must be assignee or moderator).
        Output:
            Updated TaskOccurrence.
        """
        occurrence = TaskOccurrence.objects.select_related(
            'template__group', 'assigned_to'
        ).filter(id=occurrence_id).first()
        if occurrence is None:
            raise ValueError("Task occurrence not found.")

        group = occurrence.template.group
        is_assigned = str(occurrence.assigned_to_id) == actor_id
        is_moderator = GroupMembership.objects.filter(
            user_id=actor_id, group=group, role='moderator'
        ).exists()

        if not is_assigned and not is_moderator:
            raise PermissionError("Only the assigned user or a group moderator can update this task.")

        if completed:
            if group.photo_proof_required and not occurrence.photo_proof:
                raise ValueError("Photo proof is required to complete this task.")

            points = occurrence.template.difficulty * 10
            now = timezone.now()

            with transaction.atomic():
                occurrence.status = 'completed'
                occurrence.completed_at = now
                occurrence.points_earned = points
                occurrence.save(update_fields=['status', 'completed_at', 'points_earned'])

                self._update_stats(user_id=actor_id, group=group, points=points, completed_at=now)
                # TODO Step 9: call evaluate_badges.delay(user_id=actor_id, group_id=str(group.id))
        else:
            with transaction.atomic():
                occurrence.status = 'pending'
                occurrence.completed_at = None
                occurrence.points_earned = None
                occurrence.save(update_fields=['status', 'completed_at', 'points_earned'])

        return occurrence

    @staticmethod
    def _update_stats(*, user_id: str, group, points: int, completed_at) -> None:
        """Increment UserStats and update streak on User."""
        stats, _ = UserStats.objects.get_or_create(user_id=user_id, household=group)
        stats.total_tasks_completed += 1
        stats.total_points += points

        # Streak: uses User.last_streak_date (date-level granularity)
        user = User.objects.get(id=user_id)
        today = completed_at.date()
        if user.last_streak_date == today - timedelta(days=1):
            user.on_time_streak_days += 1
        elif user.last_streak_date != today:
            user.on_time_streak_days = 1
        user.longest_on_time_streak_days = max(
            user.longest_on_time_streak_days, user.on_time_streak_days
        )
        user.last_streak_date = today
        user.save(update_fields=['on_time_streak_days', 'longest_on_time_streak_days', 'last_streak_date'])

        stats.current_streak_days = user.on_time_streak_days
        stats.longest_streak_days = user.longest_on_time_streak_days
        stats.save()

    # ------------------------------------------------------------------ #
    #  Listing helpers
    # ------------------------------------------------------------------ #

    def list_user_tasks(self, *, user_id: str, group_id: str | None = None) -> dict:
        """Return occurrences for a user grouped by status bucket."""
        qs = TaskOccurrence.objects.select_related('template__group').filter(
            assigned_to_id=user_id
        )
        if group_id:
            qs = qs.filter(template__group_id=group_id)
        now = timezone.now()
        return {
            'active': list(qs.filter(
                status__in=['pending', 'in_progress', 'snoozed'],
                deadline__lte=now + timedelta(days=1),
            )),
            'upcoming': list(qs.filter(
                status='pending',
                deadline__gt=now + timedelta(days=1),
            )),
            'completed': list(qs.filter(status='completed').order_by('-completed_at')[:20]),
        }

    def list_group_tasks(self, *, group_id: str, actor_id: str) -> list[TaskOccurrence]:
        """Return all occurrences for a group (actor must be a member)."""
        if not GroupMembership.objects.filter(user_id=actor_id, group_id=group_id).exists():
            raise PermissionError("Not a member of this group.")
        return list(
            TaskOccurrence.objects.select_related('template', 'assigned_to')
            .filter(template__group_id=group_id)
            .order_by('deadline')
        )
