"""Django Channels WebSocket consumer for ChoreSync real-time features."""
from __future__ import annotations

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


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
            await self.close(code=4001)
            return

        if self.channel_layer is None:
            await self.close(code=4002)
            return

        self.user = user
        self.user_group = f'user_{user.id}'
        self.household_groups: list[str] = []

        # Join personal group
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        # Join one channel group per household
        group_ids = await self._get_group_ids(user.id)
        for gid in group_ids:
            name = f'household_{gid}'
            self.household_groups.append(name)
            await self.channel_layer.group_add(name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        if not hasattr(self, 'user'):
            return

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
            'group_id': event['group_id'],
            'sender_id': event['sender_id'],
            'username': event['username'],
            'body': event['body'],
            'sent_at': event['sent_at'],
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

        await self.channel_layer.group_send(
            f'household_{group_id}',
            {
                'type': 'chat_broadcast',
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
            'action_url': n.action_url or '',
        }
