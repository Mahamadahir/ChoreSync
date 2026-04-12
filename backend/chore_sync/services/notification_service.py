"""Notification orchestration services for ChoreSync."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

logger = logging.getLogger(__name__)

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
        task_swap_id: int | None = None,
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
            action_url: Optional web fallback path. Do not treat this as the canonical
                        notification target; clients must resolve navigation from the
                        structured FK fields (task_occurrence_id, group_id, etc.).
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
            task_swap_id=task_swap_id,
            task_proposal_id=task_proposal_id,
            message_id=message_id,
            action_url=action_url,
        )
        self.fan_out_realtime(
            recipient_id=recipient_id,
            notification_id=str(notification.id),
        )
        # Also publish to SSE for web listeners that choose to react to notification
        # events. CalendarView reloads events on any SSE message; this is not a
        # canonical mobile delivery path (mobile uses WebSocket or polls REST).
        # Using notification.id as the SSE event_id lets reconnecting clients
        # replay missed notifications via Last-Event-ID.
        # Best-effort Expo push for backgrounded devices (non-blocking thread)
        import threading
        threading.Thread(
            target=self._send_expo_push,
            args=(recipient_id, notification),
            daemon=True,
        ).start()

        try:
            from chore_sync import sse as _sse
            _sse.publish(
                int(recipient_id),
                {
                    "type": "notification",
                    "id": str(notification.id),
                    "notification_type": notification.type,
                    "title": notification.title,
                    "content": notification.content,
                    "read": notification.read,
                    "dismissed": notification.dismissed,
                    "created_at": notification.created_at.isoformat(),
                    "group_id": str(notification.group_id) if notification.group_id else None,
                    "task_occurrence_id": notification.task_occurrence_id,
                    "task_swap_id": notification.task_swap_id,
                    "task_proposal_id": notification.task_proposal_id,
                    "action_url": notification.action_url or "",
                },
                event_id=str(notification.id),
            )
        except Exception:
            pass  # SSE publish is best-effort; WebSocket path already succeeded
        return notification

    def _send_expo_push(self, recipient_id: str, notification: Notification) -> None:
        """Send an Expo push notification to all registered tokens for the user.

        Called in a daemon thread from emit_notification so it never blocks
        the main request/task path. Failures are silently logged.
        """
        try:
            from chore_sync.models import UserPushToken
            tokens = list(
                UserPushToken.objects.filter(user_id=recipient_id)
                .values_list('token', flat=True)
            )
            if not tokens:
                return

            import requests as _req
            messages = [
                {
                    'to': token,
                    'title': notification.title,
                    'body': notification.content,
                    'sound': 'default',
                    'data': {
                        'id': notification.id,
                        'type': notification.type,
                        'group_id': str(notification.group_id) if notification.group_id else None,
                        'task_occurrence_id': notification.task_occurrence_id,
                        'task_swap_id': notification.task_swap_id,
                        'task_proposal_id': notification.task_proposal_id,
                        'action_url': notification.action_url or '',
                    },
                }
                for token in tokens
            ]
            _req.post(
                'https://exp.host/--/api/v2/push/send',
                json=messages,
                headers={
                    'Accept': 'application/json',
                    'Accept-Encoding': 'gzip, deflate',
                    'Content-Type': 'application/json',
                },
                timeout=5,
            )
        except Exception:
            logger.warning(
                "_send_expo_push: failed for recipient_id=%s notification_id=%s",
                recipient_id, notification.id, exc_info=True,
            )

    def fan_out_realtime(self, *, recipient_id: str, notification_id: str) -> None:
        """Push a notification to the user's WebSocket channel group."""
        layer = get_channel_layer()
        if layer is None:
            logger.warning("fan_out_realtime: no channel layer configured — notification %s not delivered", notification_id)
            return

        layer_type = type(layer).__name__
        logger.debug("fan_out_realtime: layer=%s recipient=%s notification=%s", layer_type, recipient_id, notification_id)
        try:
            async_to_sync(layer.group_send)(
                f'user_{recipient_id}',
                {
                    'type': 'notification_message',
                    'notification_id': notification_id,
                },
            )
            logger.debug("fan_out_realtime: group_send OK → user_%s", recipient_id)
        except Exception:
            logger.exception("fan_out_realtime: group_send FAILED for notification %s", notification_id)

    # ------------------------------------------------------------------ #
    #  Preference enforcement
    # ------------------------------------------------------------------ #

    # Maps notification type prefixes/exact names → preference field name
    _TYPE_TO_PREF: ClassVar[dict[str, str]] = {
        'deadline_reminder':    'deadline_reminders',
        'task_assigned':        'task_assigned',
        'task_swap':            'task_swap',
        'swap_accepted':        'task_swap',
        'swap_rejected':        'task_swap',
        'emergency_reassignment': 'emergency_reassign',  # type emitted by task_lifecycle_service
        'emergency_reassign':   'emergency_reassign',   # legacy key kept for safety
        'emergency_accepted':   'emergency_reassign',
        'badge_earned':         'badge_earned',
        'marketplace_claim':    'marketplace_activity',
        'suggestion_pattern':   'smart_suggestions',
        'suggestion_availability': 'smart_suggestions',
        'suggestion_preference':'smart_suggestions',
        'suggestion_streak':    'smart_suggestions',
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
                logger.warning(
                    "_should_send: quiet-hours timezone check failed for recipient_id=%s",
                    recipient_id,
                    exc_info=True,
                )

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
        """Return non-dismissed notifications (read and unread) ordered by most recent."""
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
