"""Group insights and user stats analytics service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import TruncWeek
from django.utils import timezone

from chore_sync.models import (
    GroupMembership, TaskAssignmentHistory, TaskOccurrence, TaskPreference,
    UserBadge, UserStats,
)


@dataclass
class InsightsService:
    """Generates stats, badge, and fairness dashboards."""

    # ------------------------------------------------------------------ #
    #  User stats
    # ------------------------------------------------------------------ #

    def get_user_stats(self, *, user_id: str) -> list[dict]:
        """Return UserStats for the requesting user across all households.

        Output:
            List of per-household stat dicts ordered by total_points desc.
        """
        stats_qs = (
            UserStats.objects.filter(user_id=user_id)
            .select_related('household')
            .order_by('-total_points')
        )
        return [_serialize_stats(s, user_id=user_id) for s in stats_qs]

    # ------------------------------------------------------------------ #
    #  User badges
    # ------------------------------------------------------------------ #

    def get_user_badges(self, *, user_id: str) -> list[dict]:
        """Return all badges earned by the user across all households.

        Output:
            List of badge dicts ordered by most recently awarded.
        """
        badges_qs = (
            UserBadge.objects.filter(user_id=user_id)
            .select_related('badge', 'household')
            .order_by('-awarded_at')
        )
        return [_serialize_badge(ub) for ub in badges_qs]

    # ------------------------------------------------------------------ #
    #  Group / household stats
    # ------------------------------------------------------------------ #

    def get_group_stats(self, *, group_id: str, actor_id: str) -> dict:
        """Return household-level aggregates for a group.

        Inputs:
            group_id: Target group.
            actor_id: Must be a member.
        Output:
            Dict with total_tasks, completion_rate, most_completed_task,
            and fairness_distribution.
        """
        if not GroupMembership.objects.filter(
            user_id=actor_id, group_id=group_id
        ).exists():
            raise PermissionError('You are not a member of this group.')

        # Only count occurrences that have reached their deadline — future
        # pending tasks haven't been attempted yet and would skew the rate.
        now = timezone.now()
        resolved = TaskOccurrence.objects.filter(
            template__group_id=group_id,
            deadline__lte=now,
        ).count()

        completed = TaskOccurrence.objects.filter(
            template__group_id=group_id,
            status='completed',
        ).count()

        completion_rate = round(completed / resolved, 4) if resolved > 0 else 0.0

        # Most-completed task template
        most_completed = (
            TaskOccurrence.objects.filter(
                template__group_id=group_id,
                status='completed',
            )
            .values('template__id', 'template__name')
            .annotate(count=Count('id'))
            .order_by('-count')
            .first()
        )

        # Fairness distribution — all members, zero-filling those without stats
        memberships = (
            GroupMembership.objects.filter(group_id=group_id)
            .select_related('user')
        )
        stats_by_user = {
            s.user_id: s
            for s in UserStats.objects.filter(household_id=group_id)
        }
        fairness_distribution = sorted(
            [
                {
                    'user_id': str(m.user_id),
                    'username': m.user.username,
                    'total_tasks_completed': stats_by_user[m.user_id].total_tasks_completed
                        if m.user_id in stats_by_user else 0,
                    'total_points': stats_by_user[m.user_id].total_points
                        if m.user_id in stats_by_user else 0,
                    'on_time_completion_rate': stats_by_user[m.user_id].on_time_completion_rate
                        if m.user_id in stats_by_user else 0.0,
                    'current_streak_days': stats_by_user[m.user_id].current_streak_days
                        if m.user_id in stats_by_user else 0,
                }
                for m in memberships
            ],
            key=lambda x: x['total_tasks_completed'],
            reverse=True,
        )

        preference_compliance = self._get_preference_compliance(
            group_id=group_id, memberships=memberships
        )

        return {
            'resolved_tasks': resolved,
            'completed_tasks': completed,
            'completion_rate': completion_rate,
            'most_completed_task': {
                'template_id': most_completed['template__id'],
                'name': most_completed['template__name'],
                'count': most_completed['count'],
            } if most_completed else None,
            'fairness_distribution': fairness_distribution,
            'preference_compliance': preference_compliance,
        }

    def _get_preference_compliance(
        self, *, group_id: str, memberships
    ) -> list[dict]:
        """Return per-member preference compliance stats.

        For each member: how many of their assignments matched their stated
        preference (prefer/neutral/avoid/unset). The headline metric is
        avoid_pct — the fraction of assignments where the user got a task
        they explicitly marked as 'avoid'.

        Marketplace, swap, and emergency rows are excluded because the user
        voluntarily changed the assignment, so the original preference signal
        shouldn't count against compliance.
        """
        from django.db.models import CharField

        pref_subq = TaskPreference.objects.filter(
            user_id=OuterRef('user_id'),
            task_template_id=OuterRef('task_template_id'),
        ).values('preference')[:1]

        rows = (
            TaskAssignmentHistory.objects
            .filter(
                task_template__group_id=group_id,
                was_swapped=False,
                was_emergency=False,
                was_marketplace=False,
            )
            .annotate(preference=Subquery(pref_subq, output_field=CharField()))
            .values('user_id', 'preference')
            .annotate(count=Count('id'))
        )

        # Aggregate per user
        from collections import defaultdict
        buckets: dict[str, dict[str, int]] = defaultdict(lambda: {
            'prefer': 0, 'neutral': 0, 'avoid': 0, 'unset': 0,
        })
        for row in rows:
            uid = str(row['user_id'])
            pref = row['preference'] or 'unset'
            buckets[uid][pref] = buckets[uid].get(pref, 0) + row['count']

        # Build result, zero-filling members with no history
        result = []
        for m in memberships:
            uid = str(m.user_id)
            b = buckets.get(uid, {'prefer': 0, 'neutral': 0, 'avoid': 0, 'unset': 0})
            total = sum(b.values())
            result.append({
                'user_id': uid,
                'username': m.user.username,
                'total_assignments': total,
                'prefer_count': b['prefer'],
                'neutral_count': b['neutral'],
                'avoid_count': b['avoid'],
                'unset_count': b['unset'],
                'avoid_pct': round(b['avoid'] / total, 3) if total > 0 else 0.0,
                'prefer_pct': round(b['prefer'] / total, 3) if total > 0 else 0.0,
            })

        # Sort by avoid_pct descending (worst compliance first)
        result.sort(key=lambda x: x['avoid_pct'], reverse=True)
        return result


# ------------------------------------------------------------------ #
#  Serialiser helpers
# ------------------------------------------------------------------ #

def _serialize_stats(s: UserStats, user_id: str | None = None) -> dict:
    result = {
        'household_id': str(s.household_id),
        'household_name': s.household.name,
        'total_tasks_completed': s.total_tasks_completed,
        'total_points': s.total_points,
        'tasks_completed_this_week': s.tasks_completed_this_week,
        'tasks_completed_this_month': s.tasks_completed_this_month,
        'on_time_completion_rate': s.on_time_completion_rate,
        'current_streak_days': s.current_streak_days,
        'longest_streak_days': s.longest_streak_days,
        'last_updated': s.last_updated.isoformat(),
        'weekly_completions': [],
        'category_breakdown': [],
    }
    if user_id is not None:
        eight_weeks_ago = timezone.now() - timedelta(weeks=8)
        weekly_qs = (
            TaskOccurrence.objects.filter(
                assigned_to_id=user_id,
                template__group_id=s.household_id,
                status='completed',
                completed_at__gte=eight_weeks_ago,
            )
            .annotate(week=TruncWeek('completed_at'))
            .values('week')
            .annotate(count=Count('id'))
            .order_by('week')
        )
        result['weekly_completions'] = [
            {'week': row['week'].strftime('%Y-W%W'), 'count': row['count']}
            for row in weekly_qs
        ]

        category_qs = (
            TaskOccurrence.objects.filter(
                assigned_to_id=user_id,
                template__group_id=s.household_id,
                status='completed',
            )
            .values('template__category')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        result['category_breakdown'] = [
            {'category': row['template__category'] or 'Uncategorized', 'count': row['count']}
            for row in category_qs
        ]
    return result


def _serialize_badge(ub: UserBadge) -> dict:
    return {
        'badge_id': ub.badge_id,
        'name': ub.badge.name,
        'description': ub.badge.description,
        'emoji': ub.badge.emoji,
        'icon_url': ub.badge.icon_url,
        'points_value': ub.badge.points_value,
        'household_id': str(ub.household_id),
        'household_name': ub.household.name,
        'awarded_at': ub.awarded_at.isoformat(),
    }
