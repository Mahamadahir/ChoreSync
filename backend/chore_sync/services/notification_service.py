"""Notification orchestration services for ChoreSync."""
from __future__ import annotations

from dataclasses import dataclass

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from chore_sync.models import Notification


@dataclass
class NotificationService:
    """Drives in-app and real-time notification flows."""

    # ------------------------------------------------------------------ #
    #  Emit + fan-out
    # ------------------------------------------------------------------ #

    def emit_notification(
        self,
        *,
        recipient_id: str,
        notification_type: str,
        title: str,
        content: str,
        group_id: str | None = None,
        task_occurrence_id: int | None = None,
        task_proposal_id: int | None = None,
        message_id: int | None = None,
        action_url: str = "",
    ) -> Notification:
        """Create an in-app Notification record and push it over WebSocket.

        Inputs:
            recipient_id: Target user.
            notification_type: Free-form type string.
            title: Short display title.
            content: Full notification body.
            group_id / task_occurrence_id / ...: Optional FK references for deep-linking.
            action_url: Frontend route path (e.g. '/tasks/42') that the notification
                        should navigate to when clicked. Leave empty for non-actionable
                        notifications.
        Output:
            Created Notification instance.
        """
        if not self._allowed(recipient_id=recipient_id, notification_type=notification_type):
            return None  # type: ignore[return-value]

        notification = Notification.objects.create(
            recipient_id=recipient_id,
            type=notification_type,
            title=title,
            content=content,
            group_id=group_id,
            task_occurrence_id=task_occurrence_id,
            task_proposal_id=task_proposal_id,
            message_id=message_id,
            action_url=action_url,
        )
        self.fan_out_realtime(
            recipient_id=recipient_id,
            notification_id=str(notification.id),
        )
        return notification

    def fan_out_realtime(self, *, recipient_id: str, notification_id: str) -> None:
        """Push a notification to the user's WebSocket channel group.

        Uses Django Channels layer — works with InMemoryChannelLayer (dev)
        or RedisChannelLayer (production).
        """
        layer = get_channel_layer()
        if layer is None:
            return  # no channel layer configured — skip silently

        async_to_sync(layer.group_send)(
            f'user_{recipient_id}',
            {
                'type': 'notification_message',
                'notification_id': notification_id,
            },
        )

    # ------------------------------------------------------------------ #
    #  Preference enforcement
    # ------------------------------------------------------------------ #

    # Maps notification type prefixes/exact names → preference field name
    _TYPE_TO_PREF: dict[str, str] = {
        'deadline_reminder':    'deadline_reminders',
        'task_assigned':        'task_assigned',
        'task_swap':            'task_swap',
        'swap_accepted':        'task_swap',
        'swap_rejected':        'task_swap',
        'emergency_reassign':   'emergency_reassign',
        'emergency_accepted':   'emergency_reassign',
        'badge_earned':         'badge_earned',
        'marketplace_claim':    'marketplace_activity',
        'marketplace_listed':   'marketplace_activity',
        'suggestion_pattern':   'smart_suggestions',
        'suggestion_availability': 'smart_suggestions',
        'suggestion_preference':'smart_suggestions',
        'suggestion_fairness':  'smart_suggestions',
    }

    def _allowed(self, *, recipient_id: str, notification_type: str) -> bool:
        """Return False if the user has opted out of this type or is in quiet hours."""
        from chore_sync.models import NotificationPreference, User
        try:
            prefs = NotificationPreference.objects.get(user_id=recipient_id)
        except NotificationPreference.DoesNotExist:
            return True  # no prefs row → all enabled

        # Check per-type flag
        pref_field = self._TYPE_TO_PREF.get(notification_type)
        if pref_field and not getattr(prefs, pref_field, True):
            return False

        # Check quiet hours
        if prefs.quiet_hours_enabled and prefs.quiet_start and prefs.quiet_end:
            try:
                import pytz
                from datetime import datetime
                user_tz_str = User.objects.filter(id=recipient_id).values_list('timezone', flat=True).first() or 'UTC'
                # Normalise UTC+HH offset strings to a pytz-compatible name
                try:
                    user_tz = pytz.timezone(user_tz_str)
                except pytz.UnknownTimeZoneError:
                    user_tz = pytz.UTC
                now_local = timezone.now().astimezone(user_tz).time()
                qs, qe = prefs.quiet_start, prefs.quiet_end
                # Handles overnight spans (e.g. 22:00 – 08:00)
                if qs <= qe:
                    in_quiet = qs <= now_local <= qe
                else:
                    in_quiet = now_local >= qs or now_local <= qe
                if in_quiet:
                    return False
            except Exception:
                pass  # never block a notification due to tz errors

        return True

    # ------------------------------------------------------------------ #
    #  Read / dismiss
    # ------------------------------------------------------------------ #

    def mark_notification_read(self, *, notification_id: str, actor_id: str) -> Notification:
        """Mark a notification as read.

        Inputs:
            notification_id: Target notification.
            actor_id: Must be the recipient.
        Output:
            Updated Notification.
        """
        notification = Notification.objects.filter(
            id=notification_id, recipient_id=actor_id
        ).first()
        if notification is None:
            raise ValueError("Notification not found.")
        if not notification.read:
            notification.read = True
            notification.save(update_fields=['read'])
        return notification

    def dismiss_notification(self, *, notification_id: str, actor_id: str) -> Notification:
        """Mark a notification as dismissed (hidden from inbox, kept for history).

        Inputs:
            notification_id: Target notification.
            actor_id: Must be the recipient.
        Output:
            Updated Notification.
        """
        notification = Notification.objects.filter(
            id=notification_id, recipient_id=actor_id
        ).first()
        if notification is None:
            raise ValueError("Notification not found.")
        if not notification.dismissed:
            notification.dismissed = True
            notification.save(update_fields=['dismissed'])
        return notification

    # ------------------------------------------------------------------ #
    #  Listing
    # ------------------------------------------------------------------ #

    def list_active_notifications(self, *, recipient_id: str) -> list[Notification]:
        """Return unread, non-dismissed notifications ordered by most recent."""
        return list(
            Notification.objects.filter(
                recipient_id=recipient_id,
                dismissed=False,
            ).order_by('-created_at')
        )

    def list_all_notifications(
        self, *, recipient_id: str, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        """Return paginated full notification history for a user."""
        return list(
            Notification.objects.filter(recipient_id=recipient_id)
            .order_by('-created_at')[offset: offset + limit]
        )
