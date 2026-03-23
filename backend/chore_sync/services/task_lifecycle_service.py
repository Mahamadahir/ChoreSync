"""Task lifecycle coordination services for ChoreSync."""
from __future__ import annotations

import calendar as cal_module
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from chore_sync.models import (
    Event, GroupMembership, TaskOccurrence,
    TaskPreference, TaskSwap, TaskTemplate, User, UserStats,
)
from chore_sync.services.group_service import GroupOrchestrator
from chore_sync.services.notification_service import NotificationService

_notif_svc = NotificationService()


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

        # Writeback: create a calendar event on the winner's task-writeback calendar.
        try:
            from chore_sync.services.sync_providers.registry import get_task_writeback_provider
            provider = get_task_writeback_provider(winner)
            if provider:
                provider.create_task_event(occurrence)
        except Exception:
            pass  # writeback failure must never break assignment

        _notif_svc.emit_notification(
            recipient_id=str(winner.id),
            title=f"New task assigned: {template.name}",
            notification_type='task_assigned',
            content=(
                f"You have been assigned '{template.name}' "
                f"due {deadline.strftime('%d %b %Y')}."
            ),
            task_occurrence_id=occurrence.id,
            action_url=f"/tasks/{occurrence.id}",
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
            needs_proof = group.photo_proof_required or occurrence.template.photo_proof_required
            if needs_proof and not occurrence.photo_proof:
                raise ValueError("Photo proof is required to complete this task.")

            now = timezone.now()
            occurrence.status = 'completed'
            occurrence.completed_at = now

            # Calculate points via GamificationService (includes bonuses/penalties)
            from chore_sync.services.gamification_service import GamificationService
            gsvc = GamificationService()
            points = gsvc.calculate_points(occurrence)
            occurrence.points_earned = points

            with transaction.atomic():
                occurrence.save(update_fields=['status', 'completed_at', 'points_earned'])
                self._update_stats(user_id=actor_id, group=group, points=points)
                gsvc.update_streak(user_id=actor_id, group_id=str(group.id))
                gsvc.update_on_time_rate(user_id=actor_id, group_id=str(group.id))

            # Writeback: update the calendar event to reflect completion.
            try:
                from chore_sync.services.sync_providers.registry import get_task_writeback_provider
                if occurrence.assigned_to:
                    provider = get_task_writeback_provider(occurrence.assigned_to)
                    if provider:
                        provider.update_task_event(occurrence)
            except Exception:
                pass

            from chore_sync.tasks import evaluate_badges
            evaluate_badges.delay(user_id=actor_id, group_id=str(group.id))
        else:
            with transaction.atomic():
                occurrence.status = 'pending'
                occurrence.completed_at = None
                occurrence.points_earned = None
                occurrence.save(update_fields=['status', 'completed_at', 'points_earned'])

        return occurrence

    @staticmethod
    def _update_stats(*, user_id: str, group, points: int) -> None:
        """Increment UserStats totals. Streak and rate updates handled by GamificationService."""
        stats, _ = UserStats.objects.get_or_create(user_id=user_id, household=group)
        stats.total_tasks_completed += 1
        stats.total_points += points
        stats.save(update_fields=['total_tasks_completed', 'total_points'])

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

    # ------------------------------------------------------------------ #
    #  Step 8: Snooze
    # ------------------------------------------------------------------ #

    def snooze_task(self, *, occurrence_id: str, snooze_until, actor_id: str) -> TaskOccurrence:
        """Snooze a task occurrence (max 2 snoozes, snooze_until <= deadline + 24h).

        Inputs:
            occurrence_id: Target TaskOccurrence.
            snooze_until: Datetime to snooze until.
            actor_id: Must be the assigned user.
        Output:
            Updated TaskOccurrence.
        """
        occurrence = TaskOccurrence.objects.select_related('template__group').filter(
            id=occurrence_id
        ).first()
        if occurrence is None:
            raise ValueError("Task occurrence not found.")

        if str(occurrence.assigned_to_id) != actor_id:
            raise PermissionError("Only the assigned user can snooze this task.")

        if occurrence.snooze_count >= 2:
            raise ValueError("Maximum snooze limit (2) reached for this task.")

        max_snooze = occurrence.deadline + timedelta(hours=24)
        if snooze_until > max_snooze:
            raise ValueError("Cannot snooze beyond 24 hours after the deadline.")

        with transaction.atomic():
            occurrence.status = 'snoozed'
            occurrence.snoozed_until = snooze_until
            occurrence.snooze_count += 1
            occurrence.reminder_sent_at = None  # allow reminder to re-fire
            occurrence.save(update_fields=['status', 'snoozed_until', 'snooze_count', 'reminder_sent_at'])

        return occurrence

    # ------------------------------------------------------------------ #
    #  Step 8: Swap
    # ------------------------------------------------------------------ #

    def create_swap_request(
        self, *, task_id: str, from_user_id: str, reason: str = '', to_user_id: str | None = None
    ) -> TaskSwap:
        """Create a swap request for an assigned task.

        Inputs:
            task_id: TaskOccurrence to swap.
            from_user_id: Must be the current assignee.
            reason: Optional explanation.
            to_user_id: Specific target user, or None for open request.
        Output:
            Created TaskSwap.
        """
        occurrence = TaskOccurrence.objects.select_related('template__group').filter(
            id=task_id
        ).first()
        if occurrence is None:
            raise ValueError("Task occurrence not found.")

        if str(occurrence.assigned_to_id) != from_user_id:
            raise PermissionError("Only the assigned user can request a swap.")

        if TaskSwap.objects.filter(task=occurrence, status='pending').exists():
            raise ValueError("A pending swap request already exists for this task.")

        swap_type = 'direct_swap' if to_user_id else 'open_request'

        with transaction.atomic():
            swap = TaskSwap.objects.create(
                task=occurrence,
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                reason=reason,
                swap_type=swap_type,
            )

        if to_user_id:
            _notif_svc.emit_notification(
                recipient_id=to_user_id,
                title=f"Swap request: {occurrence.template.name}",
                notification_type='task_swap',
                content=(
                    f"You have been asked to swap '{occurrence.template.name}' "
                    f"due {occurrence.deadline.strftime('%d %b %Y')}."
                ),
                task_occurrence_id=occurrence.id,
            )
        else:
            # Notify all group members except the requester
            members = GroupMembership.objects.filter(
                group=occurrence.template.group
            ).exclude(user_id=from_user_id)
            for m in members:
                _notif_svc.emit_notification(
                    recipient_id=str(m.user_id),
                    title=f"Open swap: {occurrence.template.name}",
                    notification_type='task_swap',
                    content=(
                        f"A swap has been requested for '{occurrence.template.name}' "
                        f"due {occurrence.deadline.strftime('%d %b %Y')}. Can you take it?"
                    ),
                    task_occurrence_id=occurrence.id,
                )

        return swap

    def respond_to_swap_request(self, *, swap_id: str, accept: bool, actor_id: str) -> TaskSwap:
        """Accept or reject a swap request.

        Inputs:
            swap_id: Target TaskSwap.
            accept: True to accept, False to reject.
            actor_id: User responding (must be to_user for direct, any member for open).
        Output:
            Updated TaskSwap.
        """
        swap = TaskSwap.objects.select_related('task__template__group', 'from_user').filter(
            id=swap_id, status='pending'
        ).first()
        if swap is None:
            raise ValueError("Swap request not found or already resolved.")

        if swap.expires_at < timezone.now():
            raise ValueError("This swap request has expired.")

        # For direct swaps, only the target user can respond
        if swap.swap_type == 'direct_swap' and str(swap.to_user_id) != actor_id:
            raise PermissionError("This swap request was not sent to you.")

        # For open requests, any group member (except requester) can accept
        if swap.swap_type == 'open_request':
            if str(swap.from_user_id) == actor_id:
                raise PermissionError("You cannot accept your own swap request.")
            if not GroupMembership.objects.filter(
                user_id=actor_id, group=swap.task.template.group
            ).exists():
                raise PermissionError("You are not a member of this group.")

        now = timezone.now()

        with transaction.atomic():
            swap.decided_at = now
            if accept:
                swap.status = 'accepted'
                swap.to_user_id = actor_id
                swap.save(update_fields=['status', 'decided_at', 'to_user_id'])

                occurrence = swap.task
                occurrence.assigned_to_id = actor_id
                occurrence.reassignment_reason = 'swap'
                occurrence.save(update_fields=['assigned_to_id', 'reassignment_reason'])
            else:
                swap.status = 'rejected'
                swap.save(update_fields=['status', 'decided_at'])

        if accept:
            # Writeback: move the calendar event from the original assignee to the new one.
            try:
                from chore_sync.services.sync_providers.registry import get_task_writeback_provider
                occurrence = swap.task
                # Delete from old assignee's calendar.
                old_provider = get_task_writeback_provider(swap.from_user)
                if old_provider:
                    old_provider.delete_task_event(occurrence)
                # Create on new assignee's calendar.
                new_user = occurrence.assigned_to
                new_provider = get_task_writeback_provider(new_user)
                if new_provider:
                    new_provider.create_task_event(occurrence)
            except Exception:
                pass

            _notif_svc.emit_notification(
                recipient_id=str(swap.from_user_id),
                title=f"Swap accepted: {swap.task.template.name}",
                notification_type='task_swap',
                content=f"Your swap request for '{swap.task.template.name}' was accepted.",
                task_occurrence_id=swap.task_id,
                action_url=f"/tasks/{swap.task_id}",
            )
        else:
            _notif_svc.emit_notification(
                recipient_id=str(swap.from_user_id),
                title=f"Swap declined: {swap.task.template.name}",
                notification_type='task_swap',
                content=f"Your swap request for '{swap.task.template.name}' was declined.",
                task_occurrence_id=swap.task_id,
                action_url=f"/tasks/{swap.task_id}",
            )

        return swap

    # ------------------------------------------------------------------ #
    #  Step 8: Emergency reassign
    # ------------------------------------------------------------------ #

    def emergency_reassign(self, *, occurrence_id: str, actor_id: str, reason: str = '') -> TaskOccurrence:
        """Open an emergency reassignment — broadcasts to all group members.

        Inputs:
            occurrence_id: Target TaskOccurrence.
            actor_id: Must be the current assignee.
            reason: Explanation for the emergency.
        Output:
            Updated TaskOccurrence (assigned_to=None, open for acceptance).
        """
        occurrence = TaskOccurrence.objects.select_related('template__group').filter(
            id=occurrence_id
        ).first()
        if occurrence is None:
            raise ValueError("Task occurrence not found.")

        if str(occurrence.assigned_to_id) != actor_id:
            raise PermissionError("Only the assigned user can trigger an emergency reassignment.")

        # Monthly limit: max 3 emergency reassignments per user per month
        now = timezone.now()
        monthly_count = TaskOccurrence.objects.filter(
            original_assignee_id=actor_id,
            reassignment_reason='emergency',
            deadline__year=now.year,
            deadline__month=now.month,
        ).count()
        if monthly_count >= 3:
            raise ValueError("Monthly emergency reassignment limit (3) reached.")

        group = occurrence.template.group
        members = GroupMembership.objects.filter(group=group).exclude(user_id=actor_id)

        # Writeback: delete the calendar event from the current assignee before reassigning.
        try:
            from chore_sync.services.sync_providers.registry import get_task_writeback_provider
            provider = get_task_writeback_provider(occurrence.assigned_to)
            if provider:
                provider.delete_task_event(occurrence)
        except Exception:
            pass

        with transaction.atomic():
            occurrence.original_assignee_id = actor_id
            occurrence.reassignment_reason = 'emergency'
            occurrence.assigned_to = None
            occurrence.status = 'pending'
            occurrence.save(update_fields=[
                'original_assignee_id', 'reassignment_reason', 'assigned_to', 'status'
            ])

        for m in members:
            _notif_svc.emit_notification(
                recipient_id=str(m.user_id),
                title=f"Emergency: {occurrence.template.name} needs cover",
                notification_type='emergency_reassignment',
                content=(
                    f"'{occurrence.template.name}' due {occurrence.deadline.strftime('%d %b %Y')} "
                    f"needs someone to take over. Reason: {reason or 'Not specified'}."
                ),
                task_occurrence_id=occurrence.id,
                action_url=f"/tasks/{occurrence.id}",
            )

        return occurrence

    def accept_emergency(self, *, occurrence_id: str, actor_id: str) -> TaskOccurrence:
        """Accept an open emergency reassignment — first member to call this gets the task.

        Inputs:
            occurrence_id: Target TaskOccurrence (must be in emergency/unassigned state).
            actor_id: Group member accepting the task.
        Output:
            Updated TaskOccurrence.
        """
        with transaction.atomic():
            # Lock the row to prevent race conditions
            occurrence = TaskOccurrence.objects.select_for_update().select_related(
                'template__group'
            ).filter(
                id=occurrence_id,
                reassignment_reason='emergency',
                assigned_to__isnull=True,
            ).first()

            if occurrence is None:
                raise ValueError("This task is no longer available for emergency cover.")

            if str(occurrence.original_assignee_id) == actor_id:
                raise PermissionError("You cannot accept your own emergency reassignment.")

            if not GroupMembership.objects.filter(
                user_id=actor_id, group=occurrence.template.group
            ).exists():
                raise PermissionError("You are not a member of this group.")

            occurrence.assigned_to_id = actor_id
            occurrence.status = 'pending'
            occurrence.save(update_fields=['assigned_to_id', 'status'])

        # Writeback: create a calendar event for the new assignee.
        try:
            from chore_sync.services.sync_providers.registry import get_task_writeback_provider
            new_assignee = occurrence.assigned_to
            provider = get_task_writeback_provider(new_assignee)
            if provider:
                provider.create_task_event(occurrence)
        except Exception:
            pass

        # Notify original assignee (outside transaction to allow WebSocket push)
        if occurrence.original_assignee_id:
            _notif_svc.emit_notification(
                recipient_id=str(occurrence.original_assignee_id),
                title=f"Emergency covered: {occurrence.template.name}",
                notification_type='emergency_reassignment',
                content=f"Someone has taken over '{occurrence.template.name}'.",
                task_occurrence_id=occurrence.id,
                action_url=f"/tasks/{occurrence.id}",
            )

        return occurrence
