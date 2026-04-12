"""Custom ASGI middleware for ChoreSync WebSocket connections."""
from __future__ import annotations

from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async


class JWTAuthMiddleware(BaseMiddleware):
    """
    Allow mobile clients to authenticate WebSocket connections via
    a ?token=<jwt_access_token> query parameter.

    Web clients still authenticate via session cookie (handled by the inner
    AuthMiddlewareStack). This middleware runs first: if a valid token is
    present in the query string it sets scope['user'] and the inner stack
    won't override it (it only sets AnonymousUser when no session exists).
    """

    async def __call__(self, scope, receive, send):
        if scope.get('type') == 'websocket':
            qs = parse_qs(scope.get('query_string', b'').decode())
            token_list = qs.get('token')
            if token_list:
                scope['user'] = await self._user_from_token(token_list[0])
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def _user_from_token(self, raw_token: str):
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from django.contrib.auth import get_user_model
            User = get_user_model()
            token = AccessToken(raw_token)
            return User.objects.get(id=token['user_id'])
        except Exception:
            from django.contrib.auth.models import AnonymousUser
            return AnonymousUser()
