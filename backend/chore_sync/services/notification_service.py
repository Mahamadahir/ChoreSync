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
    ) -> Notification:
        """Create an in-app Notification record and push it over WebSocket.

        Inputs:
            recipient_id: Target user.
            notification_type: One of Notification.TYPE_CHOICES keys.
            title: Short display title.
            content: Full notification body.
            group_id / task_occurrence_id / ...: Optional FK references for deep-linking.
        Output:
            Created Notification instance.
        """
        notification = Notification.objects.create(
            recipient_id=recipient_id,
            type=notification_type,
            title=title,
            content=content,
            group_id=group_id,
            task_occurrence_id=task_occurrence_id,
            task_proposal_id=task_proposal_id,
            message_id=message_id,
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
