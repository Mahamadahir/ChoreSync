from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Q

logger = logging.getLogger(__name__)

User = get_user_model()


@shared_task
def send_verification_email_task(user_id: int) -> None:
    # Import inside task to avoid circular import at module load
    from chore_sync.services.auth_service import AccountService

    svc = AccountService()
    user = User.objects.filter(id=user_id).first()
    if not user:
        return
    svc.start_email_verification(user)


@shared_task
def confirm_suggested_assignment(occurrence_id: int) -> dict:
    """Auto-confirm a streak suggestion if the user has not responded within the window.

    Called by a Celery countdown scheduled in _assign_with_streak_window().
    Only fires for streak suggestions (status='suggested'). Normal pipeline
    assignments are direct ('pending') and never reach this task.
    """
    from chore_sync.models import TaskOccurrence
    from chore_sync.services.task_lifecycle_service import TaskLifecycleService

    occurrence = (
        TaskOccurrence.objects
        .select_related('template__group', 'assigned_to')
        .filter(id=occurrence_id, status='suggested')
        .first()
    )
    if not occurrence:
        return {'skipped': 'already_resolved', 'occurrence_id': occurrence_id}

    TaskLifecycleService._confirm_assignment(occurrence)
    return {'confirmed': occurrence_id}


@shared_task
def spawn_next_occurrence(template_id: str) -> dict:
    """Advance next_due and create the next single occurrence for one template.

    Called as a Celery task after a task is completed so the completion
    HTTP response is not blocked by assignment logic.
    """
    from chore_sync.models import TaskTemplate
    from chore_sync.services.task_lifecycle_service import TaskLifecycleService

    template = TaskTemplate.objects.filter(id=template_id, active=True).first()
    if template is None:
        return {'skipped': 'template_not_found', 'template_id': template_id}

    # Advance next_due by one interval so _next_deadline returns the correct
    # following deadline rather than the one we just completed.
    TaskLifecycleService._advance_next_due(template)

    svc = TaskLifecycleService()
    try:
        created = svc.generate_recurring_instances(task_template_id=template_id)
        return {'template_id': template_id, 'occurrences_created': len(created)}
    except Exception:
        logger.exception("spawn_next_occurrence: failed for template_id=%s", template_id)
        return {'template_id': template_id, 'occurrences_created': 0, 'error': True}


@shared_task
def auto_reassign_emergency_orphan(occurrence_id: int) -> dict:
    """Pipeline-reassign an emergency occurrence if no one has accepted it yet.

    Scheduled by emergency_reassign() with a proportional countdown:
        wait = max(30 min, min(6 h, time_until_deadline * 0.4))
    If the deadline is under 2 hours away when the emergency is triggered,
    a short 5-minute window is used instead so the task isn't left unattended.

    The original assignee is excluded from the pipeline pool — they already
    said they can't do it. Falls back to the full pool if the group has only
    one member.
    """
    from chore_sync.models import TaskOccurrence
    from chore_sync.services.task_lifecycle_service import TaskLifecycleService

    occurrence = (
        TaskOccurrence.objects
        .select_related('template__group')
        .filter(id=occurrence_id, assigned_to__isnull=True, reassignment_reason='emergency')
        .first()
    )
    if occurrence is None:
        return {'skipped': 'already_resolved', 'occurrence_id': occurrence_id}

    excluded: set[str] = set()
    if occurrence.original_assignee_id:
        excluded.add(str(occurrence.original_assignee_id))

    try:
        TaskLifecycleService().assign_occurrence(occurrence, excluded_ids=excluded or None)
        logger.info(
            "auto_reassign_emergency_orphan: reassigned occurrence_id=%s via pipeline", occurrence_id
        )
        return {'assigned': occurrence_id}
    except Exception:
        logger.exception(
            "auto_reassign_emergency_orphan: pipeline failed for occurrence_id=%s", occurrence_id
        )
        return {'error': True, 'occurrence_id': occurrence_id}


@shared_task
def generate_daily_occurrences() -> dict:
    """Safety-net gap-fill: create a next occurrence for any template that has none active.

    Under the one-active-occurrence model, spawn_next_occurrence handles
    creation immediately after each completion. This periodic task is a
    fallback that catches edge cases: server restarts mid-task, worker
    failures, manual DB edits, or newly created templates.
    """
    from chore_sync.models import TaskOccurrence, TaskTemplate
    from chore_sync.services.task_lifecycle_service import TaskLifecycleService

    active_statuses = TaskLifecycleService._ACTIVE_STATUSES | {'overdue'}

    # Templates that currently have at least one active/overdue occurrence
    templates_with_active = set(
        TaskOccurrence.objects.filter(
            template__active=True,
            status__in=active_statuses,
        ).values_list('template_id', flat=True).distinct()
    )

    # Templates with no active occurrence at all — these need gap-filling
    gap_templates = (
        TaskTemplate.objects
        .filter(active=True)
        .exclude(id__in=templates_with_active)
        .values_list('id', flat=True)
    )

    svc = TaskLifecycleService()
    total_created = 0
    processed = 0

    for template_id in gap_templates:
        processed += 1
        try:
            created = svc.generate_recurring_instances(task_template_id=str(template_id))
            total_created += len(created)
        except Exception:
            logger.exception("generate_daily_occurrences: failed for template_id=%s", template_id)

    return {'templates_gap_filled': processed, 'occurrences_created': total_created}


@shared_task
def dispatch_deadline_reminders() -> dict:
    """Send deadline reminder notifications at three windows: 24h, 3h, and at-due-time.

    Each window uses select_for_update(skip_locked=True) inside a transaction so
    concurrent Celery workers cannot claim the same rows. The sentinel flag is
    written inside the transaction (before commit) so that any other worker that
    was skipped will find the flag already set when it runs its own query.
    """
    from django.db import transaction
    from django.utils import timezone
    from datetime import timedelta
    from chore_sync.models import TaskOccurrence
    from chore_sync.services.notification_service import NotificationService

    now = timezone.now()
    nsvc = NotificationService()
    sent = 0

    # ── 24-hour window ──────────────────────────────────────────────────
    with transaction.atomic():
        occs_24h = list(
            TaskOccurrence.objects
            .select_related('template', 'assigned_to')
            .select_for_update(skip_locked=True)
            .filter(
                status__in=['pending', 'snoozed'],
                deadline__gt=now,
                deadline__lte=now + timedelta(hours=24),
                reminder_sent_at__isnull=True,
                assigned_to__isnull=False,
            )
        )
        for occ in occs_24h:
            occ.reminder_sent_at = now
            occ.save(update_fields=['reminder_sent_at'])
    for occ in occs_24h:
        nsvc.emit_notification(
            recipient_id=str(occ.assigned_to_id),
            notification_type='deadline_reminder',
            title=f"Reminder: {occ.template.name} due in 24 hours",
            content=f"'{occ.template.name}' is due {occ.deadline.strftime('%d %b %Y %H:%M')}.",
            task_occurrence_id=occ.id,
            action_url=f"/tasks/{occ.id}",
        )
        sent += 1

    # ── 3-hour window ───────────────────────────────────────────────────
    with transaction.atomic():
        occs_3h = list(
            TaskOccurrence.objects
            .select_related('template', 'assigned_to')
            .select_for_update(skip_locked=True)
            .filter(
                status__in=['pending', 'snoozed'],
                deadline__gt=now + timedelta(hours=2, minutes=50),
                deadline__lte=now + timedelta(hours=3, minutes=10),
                reminder_3h_sent=False,
                assigned_to__isnull=False,
            )
        )
        for occ in occs_3h:
            occ.reminder_3h_sent = True
            occ.save(update_fields=['reminder_3h_sent'])
    for occ in occs_3h:
        nsvc.emit_notification(
            recipient_id=str(occ.assigned_to_id),
            notification_type='deadline_reminder',
            title=f"Due in 3 hours: {occ.template.name}",
            content=f"'{occ.template.name}' is due at {occ.deadline.strftime('%H:%M')}. Don't forget!",
            task_occurrence_id=occ.id,
            action_url=f"/tasks/{occ.id}",
        )
        sent += 1

    # ── At-due-time window ──────────────────────────────────────────────
    with transaction.atomic():
        occs_due = list(
            TaskOccurrence.objects
            .select_related('template', 'assigned_to')
            .select_for_update(skip_locked=True)
            .filter(
                status__in=['pending', 'snoozed'],
                deadline__gte=now - timedelta(minutes=5),
                deadline__lte=now + timedelta(minutes=5),
                reminder_due_sent=False,
                assigned_to__isnull=False,
            )
        )
        for occ in occs_due:
            occ.reminder_due_sent = True
            occ.save(update_fields=['reminder_due_sent'])
    for occ in occs_due:
        nsvc.emit_notification(
            recipient_id=str(occ.assigned_to_id),
            notification_type='deadline_reminder',
            title=f"Due now: {occ.template.name}",
            content=f"'{occ.template.name}' is due right now.",
            task_occurrence_id=occ.id,
            action_url=f"/tasks/{occ.id}",
        )
        sent += 1

    return {'reminders_sent': sent}


@shared_task
def mark_overdue_tasks() -> dict:
    """Mark pending tasks past their deadline as overdue and notify assignees."""
    from django.db import transaction
    from django.utils import timezone
    from chore_sync.models import TaskOccurrence
    from chore_sync.services.notification_service import NotificationService

    now = timezone.now()
    nsvc = NotificationService()

    with transaction.atomic():
        occurrences = list(
            TaskOccurrence.objects
            .select_related('template', 'assigned_to')
            .select_for_update(skip_locked=True)
            .filter(
                status='pending',
                deadline__lt=now,
                assigned_to__isnull=False,
            )
        )
        if occurrences:
            TaskOccurrence.objects.filter(
                id__in=[o.id for o in occurrences]
            ).update(status='overdue')

    for occurrence in occurrences:
        nsvc.emit_notification(
            recipient_id=str(occurrence.assigned_to_id),
            notification_type='deadline_reminder',
            title=f"Overdue: {occurrence.template.name}",
            content=(
                f"'{occurrence.template.name}' was due "
                f"{occurrence.deadline.strftime('%d %b %Y %H:%M')} and is now overdue."
            ),
            task_occurrence_id=occurrence.id,
            action_url=f"/tasks/{occurrence.id}",
        )

    return {'marked_overdue': len(occurrences)}


@shared_task
def cleanup_expired_swaps() -> dict:
    """Delete pending swap requests that have passed their expiry."""
    from django.utils import timezone
    from chore_sync.models import TaskSwap

    deleted, _ = TaskSwap.objects.filter(
        status='pending',
        expires_at__lt=timezone.now(),
    ).delete()

    return {'swaps_deleted': deleted}


@shared_task
def recalculate_leaderboard() -> dict:
    """Recalculate UserStats totals from TaskOccurrence aggregates for all groups."""
    from django.db.models import Count, Sum
    from chore_sync.models import Group, TaskOccurrence, UserStats

    groups = Group.objects.prefetch_related('members').all()
    updated = 0

    for group in groups:
        for membership in group.members.select_related('user').all():
            user = membership.user
            agg = TaskOccurrence.objects.filter(
                assigned_to=user,
                template__group=group,
                status='completed',
            ).aggregate(
                total_completed=Count('id'),
                total_points=Sum('points_earned'),
            )

            stats, _ = UserStats.objects.get_or_create(user=user, group=group)
            stats.total_tasks_completed = agg['total_completed'] or 0
            stats.total_points = agg['total_points'] or 0
            stats.save(update_fields=['total_tasks_completed', 'total_points'])
            updated += 1

    return {'stats_updated': updated}


@shared_task
def evaluate_badges(user_id: str, group_id: str) -> dict:
    """Evaluate badge criteria for a user after a task completion. Called on-demand."""
    from chore_sync.services.gamification_service import GamificationService

    awarded = GamificationService().evaluate_badges(user_id=user_id, group_id=group_id)
    return {'badges_awarded': len(awarded), 'badges': awarded}


@shared_task(bind=True, max_retries=8, default_retry_delay=120)
def initial_google_sync_task(self, calendar_id: int) -> dict:
    """
    Full initial sync for a Google calendar. Runs on the calendar_sync queue.

    - Sets paused=True to suppress incremental webhook syncs during the bulk pull.
    - On 429 rate-limit, saves progress (checkpoint_date) and retries with
      exponential back-off (120 * 2^retry seconds, max 8 retries ~4.5 hours).
    - Registers the watch channel only after the sync completes (avoids race).
    - Uses active_task_id to prevent duplicate concurrent syncs.
    """
    import datetime
    from googleapiclient.errors import HttpError
    from django.utils import timezone
    from chore_sync.models import Calendar, GoogleCalendarSync
    from chore_sync.services.google_calendar_service import GoogleCalendarService

    cal = Calendar.objects.select_related('user').filter(id=calendar_id).first()
    if not cal:
        return {'error': 'calendar_not_found', 'calendar_id': calendar_id}

    sync_state, _ = GoogleCalendarSync.objects.get_or_create(calendar=cal)

    # Deduplication: if another task is already running for this calendar, bail out.
    task_id = self.request.id
    if sync_state.active_task_id and sync_state.active_task_id != task_id:
        return {'skipped': 'duplicate_task', 'calendar_id': calendar_id}

    sync_state.active_task_id = task_id
    sync_state.paused = True
    sync_state.save(update_fields=['active_task_id', 'paused'])

    svc = GoogleCalendarService(user=cal.user)

    try:
        # Monthly chunking: 2 years back → 2 years ahead.
        # Each successfully processed month advances the checkpoint so that a
        # retry or crash can resume rather than restart from scratch.
        today = timezone.now().date()
        sync_start = today.replace(year=today.year - 2, month=1, day=1)
        sync_end = today.replace(year=today.year + 2, month=12, day=31)
        checkpoint = sync_state.checkpoint_date or sync_start

        current = checkpoint
        while current <= sync_end:
            # Compute the start of the next calendar month.
            if current.month == 12:
                next_month = current.replace(year=current.year + 1, month=1, day=1)
            else:
                next_month = current.replace(month=current.month + 1, day=1)

            time_min = datetime.datetime(
                current.year, current.month, current.day,
                tzinfo=datetime.timezone.utc,
            ).isoformat()
            chunk_end = min(next_month, sync_end + datetime.timedelta(days=1))
            time_max = datetime.datetime(
                chunk_end.year, chunk_end.month, chunk_end.day,
                tzinfo=datetime.timezone.utc,
            ).isoformat()

            try:
                svc._sync_chunk(cal, sync_state, time_min=time_min, time_max=time_max)
            except HttpError as exc:
                status = exc.resp.status if exc.resp is not None else None
                is_rate_limit = status in (429, 403) and (
                    status == 429 or 'rateLimitExceeded' in str(exc) or 'userRateLimitExceeded' in str(exc)
                )
                if is_rate_limit:
                    # Rate limited: persist checkpoint and retry with back-off.
                    sync_state.checkpoint_date = current
                    sync_state.save(update_fields=['checkpoint_date'])
                    retries = self.request.retries
                    backoff = 120 * (2 ** retries)  # 2m, 4m, 8m … ~4.5h total
                    raise self.retry(exc=exc, countdown=backoff)
                raise

            # Chunk done — advance checkpoint.
            sync_state.checkpoint_date = next_month
            sync_state.save(update_fields=['checkpoint_date'])
            current = next_month

        # All chunks complete — clear state and register watch channel.
        sync_state.paused = False
        sync_state.checkpoint_date = None
        sync_state.active_task_id = None
        sync_state.save(update_fields=['paused', 'checkpoint_date', 'active_task_id'])

        svc.ensure_watch_channel(cal)

        # Notify the user and push an SSE event so the calendar view reloads automatically.
        try:
            from chore_sync.services.notification_service import NotificationService
            from chore_sync import sse as sse_module
            NotificationService().emit_notification(
                recipient_id=str(cal.user_id),
                notification_type="calendar_sync_complete",
                title="Calendar synced",
                content=f'"{cal.name}" finished syncing with Google Calendar.',
                action_url="/calendar",
            )
            sse_module.publish(cal.user_id, {"type": "calendar_sync", "calendar_id": cal.id})
        except Exception:
            pass  # Non-critical — don't fail the task if notification creation fails

        return {'status': 'complete', 'calendar_id': calendar_id}

    except Exception as exc:
        # Unexpected failure: unblock so webhooks and catch-up can still run.
        sync_state.paused = False
        sync_state.active_task_id = None
        sync_state.save(update_fields=['paused', 'active_task_id'])
        raise


@shared_task
def renew_google_watch_channels() -> dict:
    """
    Renew Google push-notification watch channels that are close to expiry
    (within 30 minutes). Runs daily at 03:00.
    """
    import datetime
    from django.utils import timezone
    from chore_sync.models import GoogleCalendarSync
    from chore_sync.services.google_calendar_service import GoogleCalendarService

    margin = datetime.timedelta(minutes=30)
    soon = timezone.now() + margin

    # Calendars whose channel expires within the next 30 minutes (or has already expired).
    expiring = GoogleCalendarSync.objects.select_related('calendar__user').filter(
        watch_expires_at__lte=soon,
        paused=False,
    )

    renewed = 0
    failed = 0
    for sync_state in expiring:
        cal = sync_state.calendar
        try:
            svc = GoogleCalendarService(user=cal.user)
            svc.ensure_watch_channel(cal)
            renewed += 1
        except Exception:
            logger.exception(
                "renew_google_watch_channels: failed for calendar_id=%s user_id=%s",
                cal.id, cal.user_id,
            )
            failed += 1

    return {'renewed': renewed, 'failed': failed}


@shared_task
def catchup_google_calendar_sync() -> dict:
    """
    Safety-net incremental sync for calendars whose watch channel has expired
    (meaning they may have missed webhook notifications). Runs every 6 hours.

    Healthy calendars with an active watch channel are skipped instantly.
    """
    from django.utils import timezone
    from chore_sync.models import GoogleCalendarSync
    from chore_sync.services.google_calendar_service import GoogleCalendarService

    now = timezone.now()

    stale = GoogleCalendarSync.objects.select_related('calendar__user').filter(
        watch_expires_at__lt=now,
        paused=False,
    )

    synced = 0
    failed = 0
    for sync_state in stale:
        cal = sync_state.calendar
        try:
            svc = GoogleCalendarService(user=cal.user)
            # Incremental sync (uses sync_token if available).
            svc.sync_events(calendar=cal)
            synced += 1
        except Exception:
            logger.exception(
                "catchup_google_calendar_sync: failed for calendar_id=%s user_id=%s",
                cal.id, cal.user_id,
            )
            failed += 1

    return {'synced': synced, 'failed': failed}


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def initial_outlook_sync_task(self, calendar_id: int) -> dict:
    """
    Full initial delta sync for a Microsoft Outlook calendar.
    Runs on the calendar_sync queue.

    On 429 rate-limit, retries with exponential back-off (60 * 2^retry seconds).
    Uses OutlookCalendarService.sync_events() which handles delta links automatically:
    first call = full sync, subsequent calls = incremental via deltaLink.
    """
    from chore_sync.models import Calendar, OutlookCalendarSync
    from chore_sync.services.outlook_calendar_service import OutlookCalendarService

    cal = Calendar.objects.select_related('user').filter(id=calendar_id).first()
    if not cal:
        return {'error': 'calendar_not_found', 'calendar_id': calendar_id}

    OutlookCalendarSync.objects.get_or_create(calendar=cal)

    try:
        svc = OutlookCalendarService(user=cal.user)
        count = svc.sync_events(calendar=cal)
        try:
            from chore_sync.services.notification_service import NotificationService
            from chore_sync import sse as sse_module
            NotificationService().emit_notification(
                recipient_id=str(cal.user_id),
                notification_type="calendar_sync_complete",
                title="Calendar synced",
                content=f'"{cal.name}" finished syncing with Outlook.',
                action_url="/calendar",
            )
            sse_module.publish(cal.user_id, {"type": "calendar_sync", "calendar_id": cal.id})
        except Exception:
            pass
        return {'status': 'complete', 'calendar_id': calendar_id, 'events_synced': count}
    except Exception as exc:
        # Retry on 429 or 503 with back-off.
        status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
        if status_code in (429, 503):
            retries = self.request.retries
            backoff = 60 * (2 ** retries)
            raise self.retry(exc=exc, countdown=backoff)
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def incremental_outlook_sync_task(self, calendar_id: int) -> dict:
    """Incremental delta sync for an Outlook calendar, triggered by Graph webhooks."""
    from chore_sync.models import Calendar
    from chore_sync.services.outlook_calendar_service import OutlookCalendarService
    from chore_sync import sse as sse_module

    cal = Calendar.objects.select_related('user').filter(id=calendar_id).first()
    if not cal:
        return {'error': 'calendar_not_found', 'calendar_id': calendar_id}
    try:
        svc = OutlookCalendarService(user=cal.user)
        count = svc.sync_events(calendar=cal)
        sse_module.publish(cal.user_id, {"type": "calendar_sync", "calendar_id": cal.id})
        return {'status': 'complete', 'calendar_id': calendar_id, 'events_synced': count}
    except Exception as exc:
        status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
        if status_code in (429, 503):
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
        raise


@shared_task
def renew_outlook_subscriptions() -> dict:
    """
    Create or extend Graph change-notification subscriptions for all Outlook
    calendars whose subscription expires within the next hour. Runs every 2 hours.
    """
    import datetime
    from django.utils import timezone
    from chore_sync.models import OutlookCalendarSync
    from chore_sync.services.outlook_calendar_service import OutlookCalendarService

    threshold = timezone.now() + datetime.timedelta(hours=1)

    # Renew subscriptions that are expiring soon OR have never been created
    due = OutlookCalendarSync.objects.select_related('calendar__user').filter(
        Q(subscription_expires_at__lt=threshold) | Q(subscription_expires_at__isnull=True)
    )

    from django.conf import settings as _s
    if not getattr(_s, 'BACKEND_BASE_URL', ''):
        return {'renewed': 0}

    renewed = 0
    for sync_state in due:
        cal = sync_state.calendar
        if not cal or not cal.user:
            continue
        try:
            svc = OutlookCalendarService(user=cal.user)
            svc.renew_subscription(cal)
            renewed += 1
        except Exception:
            logger.exception(
                "renew_outlook_subscriptions: failed for calendar_id=%s user_id=%s",
                cal.id, cal.user_id,
            )

    return {'renewed': renewed}


@shared_task
def refresh_outlook_tokens() -> dict:
    """
    Proactively refresh Microsoft Graph access tokens that are within 10 minutes
    of expiry. Runs every 30 minutes so tokens never expire mid-request.
    """
    import datetime
    from django.utils import timezone
    from chore_sync.models import ExternalCredential
    from chore_sync.services.outlook_calendar_service import OutlookCalendarService

    margin = datetime.timedelta(minutes=10)
    soon = timezone.now() + margin

    expiring = ExternalCredential.objects.filter(
        provider="microsoft",
        expires_at__lte=soon,
    ).select_related('user')

    refreshed = 0
    failed = 0
    for cred in expiring:
        try:
            svc = OutlookCalendarService(user=cred.user)
            svc._get_access_token()  # refreshes and persists if needed
            refreshed += 1
        except Exception:
            logger.exception(
                "refresh_outlook_tokens: failed to refresh token for user_id=%s",
                cred.user_id,
            )
            failed += 1

    return {'refreshed': refreshed, 'failed': failed}


@shared_task
def close_expired_vote_windows() -> dict:
    """Close voting-mode proposals whose deadline has passed without a majority. Runs every 15 min."""
    from django.utils import timezone
    from chore_sync.models import TaskProposal
    from chore_sync.services.proposal_service import ProposalService

    expired_ids = list(
        TaskProposal.objects.filter(
            state='voting',
            vote_deadline__lte=timezone.now(),
        ).values_list('id', flat=True)
    )

    svc = ProposalService()
    closed = 0
    failed = 0
    for pid in expired_ids:
        try:
            svc.close_vote_window(proposal_id=pid)
            closed += 1
        except Exception:
            logger.exception('close_expired_vote_windows: failed for proposal_id=%s', pid)
            failed += 1

    return {'closed': closed, 'failed': failed}


@shared_task
def generate_smart_suggestions() -> dict:
    """Daily at 08:00 — generate personalised smart suggestions for all active groups."""
    from chore_sync.models import Group
    from chore_sync.services.smart_suggestion_service import SmartSuggestionService

    svc = SmartSuggestionService()
    total = 0
    processed = 0
    failed = 0
    for group in Group.objects.all():
        processed += 1
        try:
            total += svc.generate_for_group(group)
        except Exception:
            logger.exception(
                "generate_smart_suggestions: failed for group_id=%s", group.id
            )
            failed += 1
    return {'groups_processed': processed, 'suggestions_created': total, 'failed': failed}


@shared_task
def cleanup_expired_marketplace_listings() -> dict:
    """Delete marketplace listings that have expired. Runs every hour."""
    from django.utils import timezone
    from chore_sync.models import MarketplaceListing
    deleted, _ = MarketplaceListing.objects.filter(expires_at__lt=timezone.now()).delete()
    return {'deleted': deleted}


@shared_task
def cleanup_stale_chatbot_sessions() -> dict:
    """Delete chatbot sessions inactive for more than 7 days. Runs daily."""
    from django.utils import timezone
    from datetime import timedelta
    from chore_sync.models import ChatbotSession
    cutoff = timezone.now() - timedelta(days=7)
    deleted, _ = ChatbotSession.objects.filter(last_active__lt=cutoff).delete()
    return {'deleted': deleted}


@shared_task
def catchup_outlook_calendar_sync() -> dict:
    """
    Safety-net incremental sync for Outlook calendars that haven't been synced
    recently (> 6 hours). Runs every 6 hours.
    """
    import datetime
    from django.utils import timezone
    from chore_sync.models import Calendar
    from chore_sync.services.outlook_calendar_service import OutlookCalendarService

    threshold = timezone.now() - datetime.timedelta(hours=6)

    stale = Calendar.objects.select_related('user').filter(
        provider="microsoft",
        include_in_availability=True,
    ).filter(
        Q(last_synced_at__lt=threshold) | Q(last_synced_at__isnull=True)
    )

    synced = 0
    failed = 0
    for cal in stale:
        try:
            svc = OutlookCalendarService(user=cal.user)
            svc.sync_events(calendar=cal)
            synced += 1
        except Exception:
            logger.exception(
                "catchup_outlook_calendar_sync: failed for calendar_id=%s user_id=%s",
                cal.id, cal.user_id,
            )
            failed += 1

    return {'synced': synced, 'failed': failed}


@shared_task
def flush_expired_jwt_tokens():
    """Prune expired entries from the JWT blacklist/outstanding token tables."""
    from rest_framework_simplejwt.token_blacklist.management.commands.flushexpiredtokens import Command
    Command().handle()
    return 'flushed'
