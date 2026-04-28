"""Smart Suggestion Service — generates personalised task suggestions for group members."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone


@dataclass
class SmartSuggestionService:
    """Generates smart suggestion notifications for all members of a group.

    Four suggestion types (all stored as Notification rows):
      1. suggestion_pattern      — user habitually does a task on a specific weekday
      2. suggestion_availability — user has a free block and unassigned tasks are waiting
      3. suggestion_preference   — user prefers a task that has an unassigned occurrence
      4. suggestion_fairness     — user is below group average; offer an extra task
    """

    # Only emit a suggestion if no identical type+user+group notification was sent in the
    # past 24 hours — prevents re-flooding on every daily run.
    _COOLDOWN_HOURS = 24

    # ------------------------------------------------------------------ #
    #  Public entry point
    # ------------------------------------------------------------------ #

    def generate_for_group(self, group) -> int:
        """Generate all suggestion types for every member of *group*.

        Returns the total count of new notifications created.
        """
        from chore_sync.models import GroupMembership
        members = list(
            GroupMembership.objects.select_related('user').filter(group=group)
        )
        total = 0
        for membership in members:
            total += self._suggest_pattern(group, membership.user)
            total += self._suggest_availability(group, membership.user)
            total += self._suggest_preference(group, membership.user)
        total += self._suggest_fairness(group, members)
        return total

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _already_sent(self, *, user, group, notification_type: str) -> bool:
        """Return True if we already emitted this suggestion type today."""
        from chore_sync.models import Notification
        cutoff = timezone.now() - timedelta(hours=self._COOLDOWN_HOURS)
        return Notification.objects.filter(
            recipient=user,
            group=group,
            type=notification_type,
            created_at__gte=cutoff,
        ).exists()

    def _emit(self, *, user, group, notification_type: str, title: str, content: str) -> bool:
        """Emit a notification if the cooldown permits. Returns True if created."""
        if self._already_sent(user=user, group=group, notification_type=notification_type):
            return False
        from chore_sync.services.notification_service import NotificationService
        NotificationService().emit_notification(
            recipient_id=str(user.id),
            notification_type=notification_type,
            title=title,
            content=content,
            action_url='/tasks',
        )
        return True

    # ------------------------------------------------------------------ #
    #  Type 1 — Pattern recognition
    # ------------------------------------------------------------------ #

    def _suggest_pattern(self, group, user) -> int:
        """Suggest tasks the user habitually completes on the same weekday.

        Triggers when the user has completed a template ≥3 times and
        ≥60% of those completions fell on the same day of the week.
        Only fires if there is a pending occurrence of that template within
        the next 7 days that is not yet assigned to the user.
        """
        from chore_sync.models import TaskOccurrence

        DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        MIN_COMPLETIONS = 3
        MIN_RATIO = 0.6

        completed = (
            TaskOccurrence.objects.filter(
                assigned_to=user,
                template__group=group,
                status='completed',
                completed_at__isnull=False,
            )
            .select_related('template')
            .values('template_id', 'template__name', 'completed_at')
        )

        # Group by template
        by_template: dict[int, list] = {}
        for row in completed:
            by_template.setdefault(row['template_id'], []).append(
                (row['template__name'], row['completed_at'])
            )

        created = 0
        now = timezone.now()
        horizon = now + timedelta(days=7)

        for template_id, entries in by_template.items():
            if len(entries) < MIN_COMPLETIONS:
                continue
            template_name = entries[0][0]
            weekday_counts = Counter(dt.weekday() for _, dt in entries)
            top_day, top_count = weekday_counts.most_common(1)[0]
            if top_count / len(entries) < MIN_RATIO:
                continue

            # Check there's an upcoming occurrence of this template not yet assigned to user
            upcoming = TaskOccurrence.objects.filter(
                template_id=template_id,
                status='pending',
                deadline__gte=now,
                deadline__lte=horizon,
            ).exclude(assigned_to=user).first()
            if not upcoming:
                continue

            day_name = DAYS[top_day]
            emitted = self._emit(
                user=user,
                group=group,
                notification_type='suggestion_pattern',
                title=f"You usually do '{template_name}' on {day_name}s",
                content=(
                    f"You've completed '{template_name}' on {day_name}s "
                    f"{top_count} time(s) before. Want it assigned to you this week?"
                ),
            )
            if emitted:
                created += 1

        return created

    # ------------------------------------------------------------------ #
    #  Type 2 — Availability-based batching
    # ------------------------------------------------------------------ #

    def _suggest_availability(self, group, user) -> int:
        """Suggest task batching when the user has a 2+ hour free block.

        Looks at the next 48 hours for a continuous gap with no
        blocking calendar events. Only fires if there are ≥2 pending
        tasks assigned to the user in that window.
        """
        from chore_sync.models import Event, TaskOccurrence

        now = timezone.now()
        horizon_48h = now + timedelta(hours=48)

        # Find blocking events in the next 48h for this user
        blocking = list(
            Event.objects.filter(
                calendar__user=user,
                calendar__include_in_availability=True,
                blocks_availability=True,
                start__lt=horizon_48h,
                end__gt=now,
            ).order_by('start').values('start', 'end')
        )

        # Find the largest free block within the next 48h
        free_block_start = None
        free_block_hours = 0.0
        cursor = now

        intervals = blocking + [{'start': horizon_48h, 'end': horizon_48h}]
        for evt in intervals:
            gap_end = evt['start']
            if gap_end > cursor:
                gap_hours = (gap_end - cursor).total_seconds() / 3600
                if gap_hours > free_block_hours:
                    free_block_hours = gap_hours
                    free_block_start = cursor
            cursor = max(cursor, evt['end'])

        if free_block_hours < 2.0 or free_block_start is None:
            return 0

        # Count pending tasks assigned to user in the next 48h
        pending_count = TaskOccurrence.objects.filter(
            assigned_to=user,
            template__group=group,
            status__in=['pending', 'snoozed'],
            deadline__lte=horizon_48h,
        ).count()

        if pending_count < 2:
            return 0

        # Format the free block as a human-friendly label
        block_label = free_block_start.strftime('%A %-I%p').replace(':00', '')
        emitted = self._emit(
            user=user,
            group=group,
            notification_type='suggestion_availability',
            title=f"You're free {block_label} — knock out {pending_count} tasks?",
            content=(
                f"You have a {free_block_hours:.0f}-hour free block starting "
                f"{block_label} and {pending_count} tasks due in the next 48 hours. "
                f"Great time to get ahead!"
            ),
        )
        return 1 if emitted else 0

    # ------------------------------------------------------------------ #
    #  Type 3 — Preference-based open tasks
    # ------------------------------------------------------------------ #

    def _suggest_preference(self, group, user) -> int:
        """Suggest unassigned occurrences for tasks the user prefers.

        Fires when TaskPreference.preference='prefer' and a pending
        occurrence of that template is currently unassigned.
        """
        from chore_sync.models import TaskOccurrence, TaskPreference

        preferred_template_ids = list(
            TaskPreference.objects.filter(
                user=user,
                task_template__group=group,
                preference='prefer',
            ).values_list('task_template_id', flat=True)
        )
        if not preferred_template_ids:
            return 0

        now = timezone.now()
        created = 0

        for template_id in preferred_template_ids:
            occurrence = TaskOccurrence.objects.filter(
                template_id=template_id,
                status='pending',
                assigned_to__isnull=True,
                deadline__gte=now,
            ).select_related('template').first()
            if not occurrence:
                continue

            emitted = self._emit(
                user=user,
                group=group,
                notification_type='suggestion_preference',
                title=f"'{occurrence.template.name}' is available — you prefer this one",
                content=(
                    f"'{occurrence.template.name}' has no one assigned yet "
                    f"and you've marked it as a preferred task. Want to take it?"
                ),
            )
            if emitted:
                created += 1

        return created

    # ------------------------------------------------------------------ #
    #  Type 4 — Fairness rebalancing
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    #  Type 5 — Streak-based pre-assignment
    # ------------------------------------------------------------------ #

    # Minimum hours remaining on deadline before we skip the streak suggestion
    # and just auto-assign immediately.
    _STREAK_MIN_HOURS = 3
    # How many consecutive completions by the same user qualify as a streak.
    _STREAK_LENGTH = 3
    # Fraction of deadline window to hold the occurrence as 'suggested'.
    _STREAK_WINDOW_RATIO = 0.33
    # Hard caps (hours) on the computed wait window.
    _STREAK_WINDOW_MIN_HOURS = 1
    _STREAK_WINDOW_MAX_HOURS = 24

    @staticmethod
    def compute_streak_window_minutes(deadline) -> int | None:
        """Return how many minutes to hold the streak suggestion open.

        Returns None if the deadline is too close to bother (< _STREAK_MIN_HOURS).
        """
        from chore_sync.services.smart_suggestion_service import SmartSuggestionService
        hours_remaining = (deadline - timezone.now()).total_seconds() / 3600
        if hours_remaining < SmartSuggestionService._STREAK_MIN_HOURS:
            return None
        raw = hours_remaining * SmartSuggestionService._STREAK_WINDOW_RATIO
        clamped = max(
            SmartSuggestionService._STREAK_WINDOW_MIN_HOURS,
            min(raw, SmartSuggestionService._STREAK_WINDOW_MAX_HOURS),
        )
        return int(clamped * 60)

    def suggest_streak_assignment(self, occurrence) -> bool:
        """Check whether the last N completions of occurrence.template were by
        the same user. If so, suggest the occurrence to that user with a
        deadline-proportional window instead of the normal 10-minute window.

        Returns True if a streak suggestion was emitted (caller should NOT
        call assign_occurrence for this occurrence).
        Returns False if no streak found (caller should proceed normally).
        """
        from chore_sync.models import TaskAssignmentHistory
        from chore_sync.services.task_lifecycle_service import TaskLifecycleService

        template = occurrence.template

        # Query the last N completed assignments for this template.
        recent = (
            TaskAssignmentHistory.objects
            .filter(task_template=template, completed=True)
            .order_by('-completed_at')
            .select_related('user')
            [:self._STREAK_LENGTH]
        )

        if len(recent) < self._STREAK_LENGTH:
            return False

        # All must be the same user.
        user_ids = {str(h.user_id) for h in recent}
        if len(user_ids) != 1:
            return False

        streak_user = recent[0].user

        # Compute the deadline-proportional window.
        window_minutes = self.compute_streak_window_minutes(occurrence.deadline)
        if window_minutes is None:
            # Deadline too close — skip streak nudge, let normal pipeline run.
            return False

        # Assign the occurrence to the streak user with the custom window.
        TaskLifecycleService()._assign_with_streak_window(
            occurrence=occurrence,
            winner=streak_user,
            window_minutes=window_minutes,
            streak_length=self._STREAK_LENGTH,
        )
        return True

    def _suggest_fairness(self, group, members) -> int:
        """Suggest an extra task to members significantly below the group average.

        Fires when a member's total_tasks_completed is >20% below the
        group average and there is at least one unassigned pending occurrence.
        """
        from chore_sync.models import TaskOccurrence, UserStats

        if not members:
            return 0

        stats_map: dict = {}
        for m in members:
            s = UserStats.objects.filter(user=m.user, group=group).first()
            stats_map[m.user] = s.total_tasks_completed if s else 0

        if not stats_map:
            return 0

        avg = sum(stats_map.values()) / len(stats_map)
        if avg == 0:
            return 0

        # Find an open unassigned task to offer
        now = timezone.now()
        open_task = TaskOccurrence.objects.filter(
            template__group=group,
            status='pending',
            assigned_to__isnull=True,
            deadline__gte=now,
        ).select_related('template').first()
        if not open_task:
            return 0

        created = 0
        for user, count in stats_map.items():
            if count >= avg * 0.8:  # within 20% of average — skip
                continue
            emitted = self._emit(
                user=user,
                group=group,
                notification_type='suggestion_fairness',
                title="Take an extra task and earn bonus points?",
                content=(
                    f"You've completed {count} tasks vs the group average of {avg:.0f}. "
                    f"'{open_task.template.name}' is unassigned — grab it for extra points!"
                ),
            )
            if emitted:
                created += 1

        return created
