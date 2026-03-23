from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db.models import Q

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


# ------------------------------------------------------------------ #
#  Step 7: Periodic tasks
# ------------------------------------------------------------------ #

@shared_task
def generate_daily_occurrences() -> dict:
    """Materialise task occurrences for the next 7 days across all active templates."""
    from chore_sync.models import TaskTemplate
    from chore_sync.services.task_lifecycle_service import TaskLifecycleService

    svc = TaskLifecycleService()
    templates = TaskTemplate.objects.filter(active=True).values_list('id', flat=True)
    total_created = 0

    for template_id in templates:
        try:
            created = svc.generate_recurring_instances(
                task_template_id=str(template_id),
                horizon_days=7,
            )
            total_created += len(created)
        except Exception:
            pass  # Don't let one broken template abort the whole run

    return {'templates_processed': len(templates), 'occurrences_created': total_created}


@shared_task
def dispatch_deadline_reminders() -> dict:
    """Send deadline reminder notifications at three windows: 24h, 3h, and at-due-time."""
    from django.utils import timezone
    from datetime import timedelta
    from chore_sync.models import TaskOccurrence
    from chore_sync.services.notification_service import NotificationService

    now = timezone.now()
    nsvc = NotificationService()
    sent = 0

    # ── 24-hour window ──────────────────────────────────────────────────
    for occ in TaskOccurrence.objects.select_related('template', 'assigned_to').filter(
        status__in=['pending', 'snoozed'],
        deadline__gt=now,
        deadline__lte=now + timedelta(hours=24),
        reminder_sent_at__isnull=True,
        assigned_to__isnull=False,
    ):
        nsvc.emit_notification(
            recipient_id=str(occ.assigned_to_id),
            notification_type='deadline_reminder',
            title=f"Reminder: {occ.template.name} due in 24 hours",
            content=f"'{occ.template.name}' is due {occ.deadline.strftime('%d %b %Y %H:%M')}.",
            task_occurrence_id=occ.id,
            action_url=f"/tasks/{occ.id}",
        )
        occ.reminder_sent_at = now
        occ.save(update_fields=['reminder_sent_at'])
        sent += 1

    # ── 3-hour window ───────────────────────────────────────────────────
    for occ in TaskOccurrence.objects.select_related('template', 'assigned_to').filter(
        status__in=['pending', 'snoozed'],
        deadline__gt=now + timedelta(hours=2, minutes=50),
        deadline__lte=now + timedelta(hours=3, minutes=10),
        reminder_3h_sent=False,
        assigned_to__isnull=False,
    ):
        nsvc.emit_notification(
            recipient_id=str(occ.assigned_to_id),
            notification_type='deadline_reminder',
            title=f"Due in 3 hours: {occ.template.name}",
            content=f"'{occ.template.name}' is due at {occ.deadline.strftime('%H:%M')}. Don't forget!",
            task_occurrence_id=occ.id,
            action_url=f"/tasks/{occ.id}",
        )
        occ.reminder_3h_sent = True
        occ.save(update_fields=['reminder_3h_sent'])
        sent += 1

    # ── At-due-time window ──────────────────────────────────────────────
    for occ in TaskOccurrence.objects.select_related('template', 'assigned_to').filter(
        status__in=['pending', 'snoozed'],
        deadline__gte=now - timedelta(minutes=5),
        deadline__lte=now + timedelta(minutes=5),
        reminder_due_sent=False,
        assigned_to__isnull=False,
    ):
        nsvc.emit_notification(
            recipient_id=str(occ.assigned_to_id),
            notification_type='deadline_reminder',
            title=f"Due now: {occ.template.name}",
            content=f"'{occ.template.name}' is due right now.",
            task_occurrence_id=occ.id,
            action_url=f"/tasks/{occ.id}",
        )
        occ.reminder_due_sent = True
        occ.save(update_fields=['reminder_due_sent'])
        sent += 1

    return {'reminders_sent': sent}


@shared_task
def mark_overdue_tasks() -> dict:
    """Mark pending tasks past their deadline as overdue and notify assignees."""
    from django.utils import timezone
    from chore_sync.models import TaskOccurrence

    now = timezone.now()
    overdue = TaskOccurrence.objects.select_related('template', 'assigned_to').filter(
        status='pending',
        deadline__lt=now,
        assigned_to__isnull=False,
    )

    from chore_sync.services.notification_service import NotificationService
    nsvc = NotificationService()

    count = 0
    ids_to_update = []
    for occurrence in overdue:
        ids_to_update.append(occurrence.id)
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
        count += 1

    TaskOccurrence.objects.filter(id__in=ids_to_update).update(status='overdue')
    return {'marked_overdue': count}


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
    """Recalculate UserStats totals from TaskOccurrence aggregates for all households."""
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

            stats, _ = UserStats.objects.get_or_create(user=user, household=group)
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


# ------------------------------------------------------------------ #
#  Step 17: Google Calendar sync tasks
# ------------------------------------------------------------------ #

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
        # Monthly chunking from checkpoint (or year 2000) up to today.
        # Each successfully processed month advances the checkpoint so that a
        # retry or crash can resume rather than restart from scratch.
        checkpoint = sync_state.checkpoint_date or datetime.date(2000, 1, 1)
        today = timezone.now().date()

        current = checkpoint
        while current <= today:
            # Compute the start of the next calendar month.
            if current.month == 12:
                next_month = current.replace(year=current.year + 1, month=1, day=1)
            else:
                next_month = current.replace(month=current.month + 1, day=1)

            time_min = datetime.datetime(
                current.year, current.month, current.day,
                tzinfo=datetime.timezone.utc,
            ).isoformat()
            chunk_end = min(next_month, today + datetime.timedelta(days=1))
            time_max = datetime.datetime(
                chunk_end.year, chunk_end.month, chunk_end.day,
                tzinfo=datetime.timezone.utc,
            ).isoformat()

            try:
                svc._sync_chunk(cal, sync_state, time_min=time_min, time_max=time_max)
            except HttpError as exc:
                if exc.resp is not None and exc.resp.status == 429:
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

        return {'status': 'complete', 'calendar_id': calendar_id}

    except Exception as exc:
        # Unexpected failure: unblock so webhooks and catch-up can still run.
        sync_state.paused = False
        sync_state.active_task_id = None
        sync_state.save(update_fields=['paused', 'active_task_id'])
        raise


# ------------------------------------------------------------------ #
#  Step 17e: Periodic calendar maintenance jobs
# ------------------------------------------------------------------ #

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
    for sync_state in expiring:
        cal = sync_state.calendar
        try:
            svc = GoogleCalendarService(user=cal.user)
            svc.ensure_watch_channel(cal)
            renewed += 1
        except Exception:
            pass  # log but don't abort the whole run

    return {'renewed': renewed}


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
    for sync_state in stale:
        cal = sync_state.calendar
        try:
            svc = GoogleCalendarService(user=cal.user)
            # Incremental sync (uses sync_token if available).
            svc.sync_events(calendar=cal)
            synced += 1
        except Exception:
            pass

    return {'synced': synced}


# ------------------------------------------------------------------ #
#  Step 14: Outlook Calendar sync tasks
# ------------------------------------------------------------------ #

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
        return {'status': 'complete', 'calendar_id': calendar_id, 'events_synced': count}
    except Exception as exc:
        import requests as req_lib
        # Retry on 429 or 503 with back-off.
        status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
        if status_code in (429, 503):
            retries = self.request.retries
            backoff = 60 * (2 ** retries)
            raise self.retry(exc=exc, countdown=backoff)
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

    renewed = 0
    for sync_state in due:
        cal = sync_state.calendar
        if not cal or not cal.user:
            continue
        # Only renew if BACKEND_BASE_URL is configured (webhooks need a public URL)
        from django.conf import settings as _s
        if not getattr(_s, 'BACKEND_BASE_URL', ''):
            break
        try:
            svc = OutlookCalendarService(user=cal.user)
            svc.renew_subscription(cal)
            renewed += 1
        except Exception:
            pass

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
    for cred in expiring:
        try:
            svc = OutlookCalendarService(user=cred.user)
            svc._get_access_token()  # refreshes and persists if needed
            refreshed += 1
        except Exception:
            pass

    return {'refreshed': refreshed}


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
    for cal in stale:
        try:
            svc = OutlookCalendarService(user=cal.user)
            svc.sync_events(calendar=cal)
            synced += 1
        except Exception:
            pass

    return {'synced': synced}
