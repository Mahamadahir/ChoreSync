"""Django Channels WebSocket consumer for ChoreSync real-time features."""
from __future__ import annotations

import json
import logging
import re

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("chore_sync")


class ChoreConsumer(AsyncWebsocketConsumer):
    """
    Handles two channel groups per connection:
      - user_{user.id}          — personal notifications
      - household_{group_id}    — one group per household the user belongs to
    """

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            logger.warning("WS connect rejected: unauthenticated (user=%s)", user)
            await self.close(code=4001)
            return

        if self.channel_layer is None:
            logger.error("WS connect rejected: no channel layer configured")
            await self.close(code=4002)
            return

        self.user = user
        self.user_group = f'user_{user.id}'
        self.household_groups: list[str] = []
        logger.info("WS connected: user=%s channel=%s layer=%s", user.username, self.channel_name, type(self.channel_layer).__name__)

        # Join personal group
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        # Join one channel group per household
        group_ids = await self._get_group_ids(user.id)
        for gid in group_ids:
            name = f'household_{gid}'
            self.household_groups.append(name)
            await self.channel_layer.group_add(name, self.channel_name)

        await self.accept()

        # ── Replay missed notifications ───────────────────────────────
        # Client passes ?since={last_notification_id} on reconnect.
        # We replay any notifications created after that ID so the client
        # never silently misses a swap request, deadline reminder, etc.
        query_string = self.scope.get('query_string', b'').decode()
        since_id = None
        for part in query_string.split('&'):
            if part.startswith('since='):
                val = part[len('since='):]
                if val.isdigit():
                    since_id = int(val)
                break

        if since_id is not None:
            missed = await self._notifications_since(since_id)
            for payload in missed:
                await self.send(text_data=json.dumps({
                    'type': 'notification',
                    'notification': payload,
                }))

    async def disconnect(self, close_code):
        if not hasattr(self, 'user'):
            return
        logger.info("WS disconnected: user=%s code=%s", self.user.username, close_code)
        await self.channel_layer.group_discard(self.user_group, self.channel_name)
        for name in getattr(self, 'household_groups', []):
            await self.channel_layer.group_discard(name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """Handle messages sent *from* the client over WebSocket.

        Expected JSON shapes:
          {"type": "ping"}
          {"type": "chat_message", "group_id": "<uuid>", "body": "..."}
        """
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get('type')

        if msg_type == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

        elif msg_type == 'chat_message':
            group_id = data.get('group_id')
            body = data.get('body', '').strip()
            if group_id and body:
                await self._handle_chat(group_id=group_id, body=body)

        elif msg_type == 'mark_read':
            group_id = data.get('group_id')
            message_ids = data.get('message_ids', [])
            if group_id and isinstance(message_ids, list) and message_ids:
                updated_group_id = await self._mark_messages_read(group_id, message_ids)
                if updated_group_id:
                    await self.channel_layer.group_send(
                        f'household_{updated_group_id["group_id"]}',
                        {
                            'type': 'receipts_broadcast',
                            'message_ids': message_ids,
                            'user_id': str(self.user.id),
                            'username': self.user.username,
                            'seen_at': updated_group_id['seen_at'],
                        },
                    )

    # ------------------------------------------------------------------ #
    #  Channel-layer message handlers (called by group_send)
    # ------------------------------------------------------------------ #

    async def notification_message(self, event):
        """Push a serialised notification to this client."""
        notification_id = event.get('notification_id')
        payload = await self._serialize_notification(notification_id)
        if payload:
            await self.send(text_data=json.dumps({
                'type': 'notification',
                'notification': payload,
            }))

    async def chat_broadcast(self, event):
        """Broadcast a chat message to all members of a household."""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'id': event['id'],
            'group_id': event['group_id'],
            'sender_id': event['sender_id'],
            'username': event['username'],
            'body': event['body'],
            'sent_at': event['sent_at'],
        }))

    async def receipts_broadcast(self, event):
        """Notify clients that certain messages have been read."""
        await self.send(text_data=json.dumps({
            'type': 'receipts_update',
            'message_ids': event['message_ids'],
            'user_id': event['user_id'],
            'username': event['username'],
            'seen_at': event['seen_at'],
        }))

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    async def _handle_chat(self, *, group_id: str, body: str) -> None:
        """Persist a chat message and fan it out to household members."""
        is_member = await self._is_member(group_id)
        if not is_member:
            return

        message = await self._save_message(group_id=group_id, body=body)
        if message is None:
            return

        # Parse @mentions and send notifications
        await self._dispatch_mention_notifications(group_id=group_id, body=body, message_id=message.id)

        await self.channel_layer.group_send(
            f'household_{group_id}',
            {
                'type': 'chat_broadcast',
                'id': message.id,
                'group_id': group_id,
                'sender_id': str(self.user.id),
                'username': self.user.username,
                'body': body,
                'sent_at': message.timestamp.isoformat(),
            },
        )

    @database_sync_to_async
    def _get_group_ids(self, user_id) -> list[str]:
        from chore_sync.models import GroupMembership
        return list(
            GroupMembership.objects.filter(user_id=user_id)
            .values_list('group_id', flat=True)
        )

    @database_sync_to_async
    def _is_member(self, group_id: str) -> bool:
        from chore_sync.models import GroupMembership
        return GroupMembership.objects.filter(
            user_id=self.user.id, group_id=group_id
        ).exists()

    @database_sync_to_async
    def _save_message(self, *, group_id: str, body: str):
        from chore_sync.models import Message
        try:
            return Message.objects.create(
                group_id=group_id,
                sender_id=self.user.id,
                content=body,
            )
        except Exception:
            return None

    @database_sync_to_async
    def _mark_messages_read(self, group_id: str, message_ids: list) -> dict | None:
        """Upsert MessageReceipt rows for the current user. Returns {group_id, seen_at} on success."""
        from django.utils import timezone
        from chore_sync.models import GroupMembership, Message, MessageReceipt
        if not GroupMembership.objects.filter(user_id=self.user.id, group_id=group_id).exists():
            return None
        valid_ids = Message.objects.filter(
            id__in=message_ids, group_id=group_id
        ).values_list('id', flat=True)
        now = timezone.now()
        for mid in valid_ids:
            MessageReceipt.objects.update_or_create(
                message_id=mid,
                user_id=self.user.id,
                defaults={'seen_at': now},
            )
        return {'group_id': group_id, 'seen_at': now.isoformat()}

    @database_sync_to_async
    def _notifications_since(self, since_id: int) -> list[dict]:
        """Return serialised notifications created after since_id for this user."""
        from chore_sync.models import Notification
        qs = (
            Notification.objects
            .filter(recipient_id=self.user.id, id__gt=since_id, dismissed=False)
            .order_by('id')
        )
        return [
            {
                'id': str(n.id),
                'type': n.type,
                'title': n.title,
                'content': n.content,
                'read': n.read,
                'dismissed': n.dismissed,
                'created_at': n.created_at.isoformat(),
                'group_id': str(n.group_id) if n.group_id else None,
                'task_occurrence_id': n.task_occurrence_id,
                'task_swap_id': n.task_swap_id,
                'task_proposal_id': n.task_proposal_id,
                'message_id': n.message_id,
                'action_url': n.action_url or '',
            }
            for n in qs
        ]

    async def _dispatch_mention_notifications(self, *, group_id: str, body: str, message_id: int) -> None:
        """Parse @all / @username mentions and emit notifications to affected users."""
        mention_all = bool(re.search(r'@all\b', body, re.IGNORECASE))
        usernames = set(re.findall(r'@(\w+)', body, re.IGNORECASE))
        usernames.discard('all')

        if not mention_all and not usernames:
            return

        await self._send_mention_notifications(
            group_id=group_id,
            body=body,
            message_id=message_id,
            mention_all=mention_all,
            usernames=usernames,
        )

    @database_sync_to_async
    def _send_mention_notifications(
        self,
        *,
        group_id: str,
        body: str,
        message_id: int,
        mention_all: bool,
        usernames: set[str],
    ) -> None:
        from chore_sync.models import Group, GroupMembership, User
        from chore_sync.services.notification_service import NotificationService

        try:
            group = Group.objects.select_related().get(id=group_id)
        except Group.DoesNotExist:
            return

        sender_id = str(self.user.id)
        sender_name = self.user.username
        preview = body[:80] + ('…' if len(body) > 80 else '')
        action_url = f'/groups/{group_id}?tab=chat'
        svc = NotificationService()

        if mention_all:
            # Notify every member except the sender
            members = GroupMembership.objects.filter(
                group_id=group_id
            ).exclude(user_id=sender_id).select_related('user')
            for m in members:
                svc.emit_notification(
                    recipient_id=m.user_id,
                    notification_type='message',
                    title=f'{sender_name} mentioned everyone in {group.name}',
                    content=preview,
                    group_id=group_id,
                    message_id=message_id,
                    action_url=action_url,
                )
        else:
            # Notify only explicitly mentioned users who are group members
            mentioned_users = User.objects.filter(
                username__in=usernames,
                group_memberships__group_id=group_id,
            ).exclude(id=sender_id)
            for user in mentioned_users:
                svc.emit_notification(
                    recipient_id=user.id,
                    notification_type='message',
                    title=f'{sender_name} mentioned you in {group.name}',
                    content=preview,
                    group_id=group_id,
                    message_id=message_id,
                    action_url=action_url,
                )

    @database_sync_to_async
    def _serialize_notification(self, notification_id: str) -> dict | None:
        from chore_sync.models import Notification
        n = Notification.objects.filter(id=notification_id).first()
        if n is None:
            return None
        return {
            'id': str(n.id),
            'type': n.type,
            'title': n.title,
            'content': n.content,
            'read': n.read,
            'dismissed': n.dismissed,
            'created_at': n.created_at.isoformat(),
            'group_id': str(n.group_id) if n.group_id else None,
            'task_occurrence_id': n.task_occurrence_id,
            'task_swap_id': n.task_swap_id,
            'task_proposal_id': n.task_proposal_id,
            'message_id': n.message_id,
            'action_url': n.action_url or '',
        }
