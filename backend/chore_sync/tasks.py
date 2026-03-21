from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model

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
    """Send a reminder notification for tasks due within the next 24 hours (once per occurrence)."""
    from django.utils import timezone
    from datetime import timedelta
    from chore_sync.models import TaskOccurrence

    now = timezone.now()
    window_end = now + timedelta(hours=24)

    pending = TaskOccurrence.objects.select_related('template', 'assigned_to').filter(
        status__in=['pending', 'snoozed'],
        deadline__gt=now,
        deadline__lte=window_end,
        reminder_sent_at__isnull=True,
        assigned_to__isnull=False,
    )

    from chore_sync.services.notification_service import NotificationService
    nsvc = NotificationService()

    sent = 0
    for occurrence in pending:
        nsvc.emit_notification(
            recipient_id=str(occurrence.assigned_to_id),
            notification_type='deadline_reminder',
            title=f"Reminder: {occurrence.template.name} due soon",
            content=(
                f"'{occurrence.template.name}' is due "
                f"{occurrence.deadline.strftime('%d %b %Y %H:%M')}."
            ),
            task_occurrence_id=occurrence.id,
        )
        occurrence.reminder_sent_at = now
        occurrence.save(update_fields=['reminder_sent_at'])
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
