"""Task lifecycle coordination services for ChoreSync."""
from __future__ import annotations

import calendar as cal_module
import logging
from dataclasses import dataclass
from datetime import timedelta

logger = logging.getLogger(__name__)

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from chore_sync.models import (
    Event, GroupMembership, TaskAssignmentHistory, TaskOccurrence,
    TaskPreference, TaskSwap, TaskTemplate, User, UserStats,
)
from chore_sync.services.group_service import GroupOrchestrator
from chore_sync.services.notification_service import NotificationService

_notif_svc = NotificationService()


@dataclass
class _PipelineResult:
    """Return type of _run_pipeline carrying the winner and full breakdown."""
    winner: 'User'
    score_breakdown: dict  # {winner_id, candidates: [...]}


@dataclass
class TaskLifecycleService:
    """Handles task occurrence generation, assignment, and completion."""

    # ------------------------------------------------------------------ #
    #  Recurrence expansion
    # ------------------------------------------------------------------ #

    @staticmethod
    def _next_deadline(template: TaskTemplate):
        """Return the single next deadline datetime for template, or None.

        Used by the one-active-occurrence model: computes exactly one future
        deadline from template.next_due for recurring templates, or returns
        next_due directly for one-off tasks.
        """
        now = timezone.now()
        start = template.next_due

        # Respect optional end date
        if template.recur_end:
            from datetime import datetime
            end_dt = datetime(
                template.recur_end.year, template.recur_end.month, template.recur_end.day,
                23, 59, 59, tzinfo=now.tzinfo,
            )
            if start > end_dt:
                return None

        if template.recurring_choice == 'none':
            return start if start >= now else None

        elif template.recurring_choice == 'weekly':
            # Advance start until it is >= now
            current = start
            while current < now:
                current += timedelta(weeks=1)
            return current

        elif template.recurring_choice == 'monthly':
            current = start
            while current < now:
                month = current.month + 1
                year = current.year
                if month > 12:
                    month, year = 1, year + 1
                max_day = cal_module.monthrange(year, month)[1]
                current = current.replace(year=year, month=month, day=min(current.day, max_day))
            return current

        elif template.recurring_choice == 'every_n_days':
            n = template.recur_value or 1
            current = start
            while current < now:
                current += timedelta(days=n)
            return current

        elif template.recurring_choice == 'custom':
            day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
            target_days = {day_map[d] for d in (template.days_of_week or [])}
            if not target_days:
                return None
            current = now.replace(
                hour=start.hour, minute=start.minute, second=0, microsecond=0
            )
            if current < now:
                current += timedelta(days=1)
            for _ in range(14):  # search up to 2 weeks ahead
                if current.weekday() in target_days:
                    return current
                current += timedelta(days=1)
            return None

        return None

    @staticmethod
    def _advance_next_due(template: TaskTemplate) -> None:
        """Advance template.next_due by one recurrence interval and save.

        Called immediately after an occurrence is completed so the next call
        to generate_recurring_instances produces the correct following deadline.
        No-op for one-off (recurring_choice='none') templates.
        """
        now = timezone.now()
        current = template.next_due

        if template.recurring_choice == 'none':
            return  # single task — no advancement

        elif template.recurring_choice == 'weekly':
            current += timedelta(weeks=1)

        elif template.recurring_choice == 'monthly':
            month = current.month + 1
            year = current.year
            if month > 12:
                month, year = 1, year + 1
            max_day = cal_module.monthrange(year, month)[1]
            current = current.replace(year=year, month=month, day=min(current.day, max_day))

        elif template.recurring_choice == 'every_n_days':
            n = template.recur_value or 1
            current += timedelta(days=n)

        elif template.recurring_choice == 'custom':
            day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
            target_days = {day_map[d] for d in (template.days_of_week or [])}
            current += timedelta(days=1)
            for _ in range(14):
                if current.weekday() in target_days:
                    break
                current += timedelta(days=1)

        # Ensure we never regress (safety net if clock skew / manual edits)
        if current <= now:
            # Push forward by the minimum interval so we don't create a stale occurrence
            current = now + timedelta(hours=1)

        template.next_due = current
        template.save(update_fields=['next_due'])

    # ------------------------------------------------------------------ #
    #  Generate recurring instances
    # ------------------------------------------------------------------ #

    # Active statuses — an occurrence in any of these blocks generation of a new one.
    _ACTIVE_STATUSES = frozenset({'suggested', 'pending', 'in_progress', 'snoozed', 'reassigned'})

    def generate_recurring_instances(self, *, task_template_id: str, horizon_days: int = 7) -> list[TaskOccurrence]:
        """Create the next single occurrence for a template if none is currently active.

        One-active-occurrence model: at most one unresolved occurrence exists
        per template at any time. A new occurrence is only created when the
        previous one has been completed, cancelled, or is overdue and considered
        expired (more than 24 h past its deadline with no resolution).

        horizon_days is kept for API compatibility but is no longer used to
        expand a window — we always create exactly one occurrence.

        Inputs:
            task_template_id: Active TaskTemplate to check and expand.
        Output:
            List containing the single newly created TaskOccurrence, or [].
        """
        template = TaskTemplate.objects.select_related('group').filter(
            id=task_template_id, active=True
        ).first()
        if template is None:
            raise ValueError("Task template not found.")

        # Guard: if an active occurrence already exists, do nothing.
        has_active = TaskOccurrence.objects.filter(
            template=template,
            status__in=self._ACTIVE_STATUSES,
        ).exists()
        if has_active:
            return []

        # Also skip if there is an overdue occurrence that hasn't been resolved
        # yet but is less than 24 h past its deadline (give members time to act).
        recent_overdue = TaskOccurrence.objects.filter(
            template=template,
            status='overdue',
            deadline__gte=timezone.now() - timedelta(hours=24),
        ).exists()
        if recent_overdue:
            return []

        deadline = self._next_deadline(template)
        if deadline is None:
            return []

        from chore_sync.services.smart_suggestion_service import SmartSuggestionService
        _streak_svc = SmartSuggestionService()

        occurrence, new = TaskOccurrence.objects.get_or_create(
            template=template,
            deadline=deadline,
        )
        if not new:
            return []  # already existed (idempotent)

        streak_fired = _streak_svc.suggest_streak_assignment(occurrence)
        if not streak_fired:
            self.assign_occurrence(occurrence)

        return [occurrence]

    # ------------------------------------------------------------------ #
    #  Assignment — 3-stage pipeline
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    #  Assignment pipeline (internal helper — no side effects)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _run_pipeline(
        occurrence: TaskOccurrence,
        excluded_ids: list[str] | None = None,
    ) -> '_PipelineResult':
        """Run the 3-stage fairness pipeline and return a _PipelineResult.

        Stage 1 — Normalised fairness score (0-1) via compute_assignment_matrix.
        Stage 2a — Explicit preference multiplier (prefer ×0.8, neutral ×1.0, avoid ×1.2).
        Stage 2b — Historical affinity multiplier (≥65% completion ×0.88, ≤25% ×1.12).
        Stage 3 — Calendar availability penalty (proportional, max +0.5).

        excluded_ids: user IDs to skip (e.g. those who already declined).
        Falls back to the full pool if all candidates are excluded.

        Returns a _PipelineResult with the winning User and a score_breakdown dict
        capturing per-candidate component scores for the "Why assigned?" feature.
        """
        from collections import defaultdict

        template = occurrence.template
        group = template.group
        deadline = occurrence.deadline

        matrix_detailed = GroupOrchestrator().compute_assignment_matrix(
            group_id=str(group.id), detailed=True
        )
        stage1: dict[str, float] = {uid: v['score'] for uid, v in matrix_detailed.items()}
        tasks_norm: dict[str, float] = {uid: v['tasks_score'] for uid, v in matrix_detailed.items()}
        time_norm: dict[str, float] = {uid: v['time_score'] for uid, v in matrix_detailed.items()}
        points_norm: dict[str, float] = {uid: v['points_score'] for uid, v in matrix_detailed.items()}

        # Strip excluded candidates (fallback: use full pool if nothing left)
        if excluded_ids:
            filtered = {uid: s for uid, s in stage1.items() if uid not in excluded_ids}
            if filtered:
                stage1 = filtered
                tasks_norm = {uid: tasks_norm[uid] for uid in stage1}
                time_norm = {uid: time_norm[uid] for uid in stage1}
                points_norm = {uid: points_norm[uid] for uid in stage1}

        # Bulk-fetch usernames for breakdown payload
        username_map: dict[str, str] = {
            str(u['id']): u['username']
            for u in User.objects.filter(id__in=stage1.keys()).values('id', 'username')
        }

        # Intermediate tracking — keyed by uid
        pref_mult:     dict[str, float] = {uid: 1.0 for uid in stage1}
        affinity_mult: dict[str, float] = {uid: 1.0 for uid in stage1}
        cal_penalty:   dict[str, float] = {uid: 0.0 for uid in stage1}

        # Stage 2a — Explicit preference multiplier.
        PREF_WEIGHT = {'prefer': 0.8, 'neutral': 1.0, 'avoid': 1.2}
        preferences = {
            str(p.user_id): p.preference
            for p in TaskPreference.objects.filter(
                task_template=template, user_id__in=stage1.keys()
            )
        }
        for uid in stage1:
            pref_mult[uid] = PREF_WEIGHT[preferences.get(uid, 'neutral')]

        # Stage 2b — Historical affinity (implicit preference from assignment history).
        #
        # For users with no explicit preference (neutral), look at how often they
        # have completed this specific task template vs how often it was assigned.
        # A high completion rate suggests natural affinity → mild boost (×0.88).
        # A low completion rate suggests repeated avoidance → mild penalty (×1.12).
        # Requires ≥3 assignments to be meaningful; ignores swapped/emergency rows
        # so the signal reflects genuine preference, not forced assignments.
        history_qs = (
            TaskAssignmentHistory.objects.filter(
                task_template=template,
                user_id__in=stage1.keys(),
                was_swapped=False,
                was_emergency=False,
            )
            .values('user_id')
            .annotate(
                assignments=Count('id'),
                completions=Count('id', filter=Q(completed=True)),
            )
        )
        for row in history_qs:
            uid = str(row['user_id'])
            if uid not in stage1:
                continue
            if preferences.get(uid, 'neutral') != 'neutral':
                continue  # explicit preference already applied — don't double-count
            if row['assignments'] < 3:
                continue  # not enough history to be reliable
            rate = row['completions'] / row['assignments']
            if rate >= 0.65:
                affinity_mult[uid] = 0.88   # implicit prefer
            elif rate <= 0.25:
                affinity_mult[uid] = 1.12   # implicit avoid

        # Stage 3 — proportional calendar penalty.
        # Window: [task_start, deadline] using estimated_mins (default 60 min).
        # Penalty = (minutes busy within window / window minutes) * 0.5
        # Fully busy → +0.5; 50% busy → +0.25; free → +0.0
        window_mins = template.estimated_mins or 60
        task_start = deadline - timedelta(minutes=window_mins)

        overlapping_events = Event.objects.filter(
            calendar__user_id__in=list(stage1.keys()),
            calendar__include_in_availability=True,
            blocks_availability=True,
            start__lt=deadline,
            end__gt=task_start,
        ).values('calendar__user_id', 'start', 'end')

        user_busy_mins: dict[str, float] = defaultdict(float)
        for ev in overlapping_events:
            uid = str(ev['calendar__user_id'])
            overlap_start = max(ev['start'], task_start)
            overlap_end = min(ev['end'], deadline)
            user_busy_mins[uid] += (overlap_end - overlap_start).total_seconds() / 60

        for uid in stage1:
            if uid in user_busy_mins:
                busy_ratio = min(user_busy_mins[uid] / window_mins, 1.0)
                cal_penalty[uid] = round(busy_ratio * 0.5, 4)

        # Compose final scores
        final_scores: dict[str, float] = {
            uid: stage1[uid] * pref_mult[uid] * affinity_mult[uid] + cal_penalty[uid]
            for uid in stage1
        }

        winner_id = min(final_scores, key=final_scores.get)
        winner = User.objects.get(id=winner_id)

        # Build score_breakdown blob for persistence
        breakdown = {
            'winner_id': winner_id,
            'candidates': [
                {
                    'user_id': uid,
                    'username': username_map.get(uid, uid[:8]),
                    'stage1_score': round(stage1[uid], 4),
                    'tasks_score': round(tasks_norm[uid], 4),
                    'time_score': round(time_norm[uid], 4),
                    'points_score': round(points_norm[uid], 4),
                    'pref_multiplier': pref_mult[uid],
                    'affinity_multiplier': affinity_mult[uid],
                    'calendar_penalty': cal_penalty[uid],
                    'final_score': round(final_scores[uid], 4),
                }
                for uid in stage1
            ],
        }

        return _PipelineResult(winner=winner, score_breakdown=breakdown)

    # ------------------------------------------------------------------ #
    #  Public assign entry point — sends suggestion notification
    # ------------------------------------------------------------------ #

    def assign_occurrence(
        self,
        occurrence: TaskOccurrence,
        excluded_ids: list[str] | None = None,
    ) -> None:
        """Directly assign a TaskOccurrence to the fairness pipeline winner.

        Runs the 3-stage scoring pipeline (fairness → preference → calendar),
        saves status='pending' immediately, records assignment history, and
        notifies the winner. No intermediate 'suggested' state.

        excluded_ids: user IDs to skip (e.g. streak decliner passed through
        from _assign_with_streak_window fallback).
        """
        result = self._run_pipeline(occurrence, excluded_ids=excluded_ids)
        winner = result.winner
        template = occurrence.template
        deadline = occurrence.deadline

        with transaction.atomic():
            occurrence.assigned_to = winner
            occurrence.status = 'pending'
            occurrence.suggestion_expires_at = None
            occurrence.suggestion_declined_ids = list(excluded_ids or [])
            occurrence.save(update_fields=[
                'assigned_to', 'status', 'suggestion_expires_at', 'suggestion_declined_ids',
            ])
            TaskAssignmentHistory.objects.create(
                user=winner,
                task_template=template,
                task_occurrence=occurrence,
                score_breakdown=result.score_breakdown,
            )

        try:
            from chore_sync.services.sync_providers.registry import get_task_writeback_provider
            provider = get_task_writeback_provider(winner)
            if provider:
                provider.create_task_event(occurrence)
        except Exception:
            logger.exception(
                "assign_occurrence: calendar writeback failed for occurrence_id=%s", occurrence.id
            )

        _notif_svc.emit_notification(
            recipient_id=str(winner.id),
            title=f"Task assigned: {template.name}",
            notification_type='task_assigned',
            content=(
                f"You've been assigned '{template.name}' "
                f"due {deadline.strftime('%d %b %Y')}."
            ),
            task_occurrence_id=occurrence.id,
            action_url=f"/tasks/{occurrence.id}",
        )

    # ------------------------------------------------------------------ #
    #  Streak-based suggestion (deadline-proportional window)
    # ------------------------------------------------------------------ #

    def _assign_with_streak_window(
        self,
        *,
        occurrence: TaskOccurrence,
        winner,
        window_minutes: int,
        streak_length: int,
    ) -> None:
        """Assign *occurrence* to *winner* as a streak suggestion.

        The suggestion window is deadline-proportional (computed by
        SmartSuggestionService.compute_streak_window_minutes) rather than
        the default 10 minutes used by assign_occurrence.
        """
        from django.utils import timezone as tz
        from datetime import timedelta

        template = occurrence.template
        deadline = occurrence.deadline
        expires_at = tz.now() + timedelta(minutes=window_minutes)
        window_hours = round(window_minutes / 60, 1)

        with transaction.atomic():
            occurrence.assigned_to = winner
            occurrence.status = 'suggested'
            occurrence.suggestion_expires_at = expires_at
            occurrence.suggestion_declined_ids = []
            occurrence.save(update_fields=[
                'assigned_to', 'status', 'suggestion_expires_at', 'suggestion_declined_ids',
            ])

        from chore_sync.tasks import confirm_suggested_assignment
        confirm_suggested_assignment.apply_async(
            kwargs={'occurrence_id': occurrence.id},
            countdown=window_minutes * 60,
        )

        _notif_svc.emit_notification(
            recipient_id=str(winner.id),
            title=f"Your usual task is ready: {template.name}",
            notification_type='suggestion_streak',
            content=(
                f"You've completed '{template.name}' the last {streak_length} times. "
                f"It's due {deadline.strftime('%d %b %Y')} — want it assigned to you again? "
                f"Respond within {window_hours}h or it auto-assigns."
            ),
            task_occurrence_id=occurrence.id,
            action_url=f"/tasks/{occurrence.id}",
        )

    # ------------------------------------------------------------------ #
    #  Confirm assignment (shared by accept + auto-timeout)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _confirm_assignment(occurrence: TaskOccurrence) -> None:
        """Transition a suggested occurrence to pending and finalise side-effects.

        Uses select_for_update inside the atomic block so that concurrent Celery
        auto-confirm and user acceptance cannot both finalize the same suggestion.
        The second caller will see status != 'suggested' and return early.
        """
        with transaction.atomic():
            # Re-fetch with a row lock; if another path already confirmed this
            # occurrence the status will no longer be 'suggested' and we bail out.
            locked = (
                TaskOccurrence.objects
                .select_for_update()
                .select_related('template__group', 'assigned_to')
                .filter(id=occurrence.id, status='suggested')
                .first()
            )
            if locked is None:
                return  # already confirmed or resolved by the concurrent path

            winner = locked.assigned_to
            template = locked.template

            locked.status = 'pending'
            locked.suggestion_expires_at = None
            locked.save(update_fields=['status', 'suggestion_expires_at'])
            TaskAssignmentHistory.objects.create(
                user=winner,
                task_template=template,
                task_occurrence=locked,
            )

        try:
            from chore_sync.services.sync_providers.registry import get_task_writeback_provider
            provider = get_task_writeback_provider(winner)
            if provider:
                provider.create_task_event(locked)
        except Exception:
            logger.exception(
                "_confirm_assignment: calendar writeback failed for occurrence_id=%s", locked.id
            )

        _notif_svc.emit_notification(
            recipient_id=str(winner.id),
            title=f"Task assigned: {template.name}",
            notification_type='task_assigned',
            content=(
                f"You've been assigned '{template.name}' "
                f"due {locked.deadline.strftime('%d %b %Y')}."
            ),
            task_occurrence_id=locked.id,
            action_url=f"/tasks/{locked.id}",
        )

    # ------------------------------------------------------------------ #
    #  Accept / decline suggestion
    # ------------------------------------------------------------------ #

    def accept_suggestion(self, *, occurrence_id: int, actor_id: str) -> TaskOccurrence:
        """Accept a pre-assignment suggestion — confirms the task immediately.

        Inputs:
            occurrence_id: Target TaskOccurrence (must be status='suggested').
            actor_id: Must be the suggested assignee.
        Output:
            Confirmed TaskOccurrence.
        """
        occurrence = TaskOccurrence.objects.select_related(
            'template__group', 'assigned_to'
        ).filter(id=occurrence_id, status='suggested').first()
        if occurrence is None:
            raise ValueError("No pending suggestion found for this task.")
        if str(occurrence.assigned_to_id) != actor_id:
            raise PermissionError("This suggestion was not sent to you.")

        self._confirm_assignment(occurrence)
        return occurrence

    def decline_suggestion(self, *, occurrence_id: int, actor_id: str) -> TaskOccurrence:
        """Decline a pre-assignment suggestion — immediately assigns the next best candidate.

        The decliner is excluded from the fallback assignment. If everyone in the
        group has declined, the original pipeline winner is force-assigned.

        Inputs:
            occurrence_id: Target TaskOccurrence (must be status='suggested').
            actor_id: Must be the suggested assignee.
        Output:
            TaskOccurrence (now pending, assigned to the fallback user).
        """
        occurrence = TaskOccurrence.objects.select_related(
            'template__group', 'assigned_to'
        ).filter(id=occurrence_id, status='suggested').first()
        if occurrence is None:
            raise ValueError("No pending suggestion found for this task.")
        if str(occurrence.assigned_to_id) != actor_id:
            raise PermissionError("This suggestion was not sent to you.")

        declined_ids = list(occurrence.suggestion_declined_ids or [])
        declined_ids.append(actor_id)

        # Fall back to the normal direct-assignment pipeline, excluding the decliner.
        # assign_occurrence handles history, calendar writeback, and notifying the new assignee.
        occurrence.suggestion_declined_ids = declined_ids
        self.assign_occurrence(occurrence, excluded_ids=declined_ids)
        return occurrence

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
            needs_proof = occurrence.template.photo_proof_required
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
                TaskAssignmentHistory.objects.filter(
                    user_id=actor_id,
                    task_occurrence=occurrence,
                    completed=False,
                ).update(completed=True, completed_at=now)

            # Writeback: update the calendar event to reflect completion.
            try:
                from chore_sync.services.sync_providers.registry import get_task_writeback_provider
                if occurrence.assigned_to:
                    provider = get_task_writeback_provider(occurrence.assigned_to)
                    if provider:
                        provider.update_task_event(occurrence)
            except Exception:
                logger.exception(
                    "toggle_occurrence_completed: calendar writeback failed for occurrence_id=%s",
                    occurrence.id,
                )

            from chore_sync.tasks import evaluate_badges, spawn_next_occurrence
            evaluate_badges.delay(user_id=actor_id, group_id=str(group.id))
            # Advance next_due and create the next occurrence asynchronously so
            # the completion response is not delayed by assignment logic.
            spawn_next_occurrence.delay(template_id=str(occurrence.template_id))
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
        qs = TaskOccurrence.objects.select_related('template__group', 'assigned_to').filter(
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
            TaskOccurrence.objects.select_related('template__group', 'assigned_to')
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
                task_swap_id=swap.id,
                action_url=f"/tasks/{occurrence.id}",
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
                    task_swap_id=swap.id,
                    action_url=f"/tasks/{occurrence.id}",
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

                # Mark original assignee's history row as swapped
                TaskAssignmentHistory.objects.filter(
                    user_id=swap.from_user_id,
                    task_occurrence=occurrence,
                ).update(was_swapped=True)
                # New history row for the accepting user
                TaskAssignmentHistory.objects.create(
                    user_id=actor_id,
                    task_template=occurrence.template,
                    task_occurrence=occurrence,
                    was_swapped=True,
                )
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
                logger.exception(
                    "respond_to_swap_request: calendar writeback failed for swap_id=%s", swap.id
                )

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
            logger.exception(
                "emergency_reassign: calendar writeback failed for occurrence_id=%s", occurrence_id
            )

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

        # Schedule auto-reassignment via pipeline if no one volunteers in time.
        # Wait = max(30 min, min(6 h, 40% of remaining time)).
        # If deadline is under 2 h away, give a 5-minute broadcast window only.
        from chore_sync.tasks import auto_reassign_emergency_orphan
        time_until = (occurrence.deadline - timezone.now()).total_seconds()
        if time_until > 0:
            if time_until < 7200:  # < 2 h — act quickly
                wait_seconds = 300  # 5 min
            else:
                wait_seconds = int(max(1800, min(21600, time_until * 0.4)))
            auto_reassign_emergency_orphan.apply_async(
                args=[occurrence.id], countdown=wait_seconds
            )
            logger.info(
                "emergency_reassign: scheduled auto-reassign for occurrence_id=%s in %ds",
                occurrence.id, wait_seconds,
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
            TaskAssignmentHistory.objects.create(
                user_id=actor_id,
                task_template=occurrence.template,
                task_occurrence=occurrence,
                was_emergency=True,
            )

        # Writeback: create a calendar event for the new assignee.
        try:
            from chore_sync.services.sync_providers.registry import get_task_writeback_provider
            new_assignee = occurrence.assigned_to
            provider = get_task_writeback_provider(new_assignee)
            if provider:
                provider.create_task_event(occurrence)
        except Exception:
            logger.exception(
                "accept_emergency: calendar writeback failed for occurrence_id=%s", occurrence_id
            )

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
