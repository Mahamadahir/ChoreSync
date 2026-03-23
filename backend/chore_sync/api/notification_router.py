"""DRF views for notification endpoints."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from chore_sync.services.notification_service import NotificationService

_svc = NotificationService()


class NotificationListAPIView(APIView):
    """GET /api/notifications/ — return active (non-dismissed) notifications."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = _svc.list_active_notifications(
            recipient_id=str(request.user.id)
        )
        return Response([_serialize(n) for n in notifications])


class NotificationHistoryAPIView(APIView):
    """GET /api/notifications/history/ — paginated full history."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            limit = max(1, min(200, int(request.query_params.get('limit', 50))))
            offset = max(0, int(request.query_params.get('offset', 0)))
        except (ValueError, TypeError):
            return Response(
                {'detail': 'limit and offset must be integers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        notifications = _svc.list_all_notifications(
            recipient_id=str(request.user.id),
            limit=limit,
            offset=offset,
        )
        return Response([_serialize(n) for n in notifications])


class NotificationReadAPIView(APIView):
    """POST /api/notifications/{pk}/read/ — mark a notification as read."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = _svc.mark_notification_read(
                notification_id=str(pk),
                actor_id=str(request.user.id),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize(notification))


class NotificationDismissAPIView(APIView):
    """POST /api/notifications/{pk}/dismiss/ — dismiss a notification."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = _svc.dismiss_notification(
                notification_id=str(pk),
                actor_id=str(request.user.id),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize(notification))


# ------------------------------------------------------------------ #
#  Serialiser helper
# ------------------------------------------------------------------ #

def _serialize(n) -> dict:
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
        'task_proposal_id': n.task_proposal_id,
        'message_id': n.message_id,
        'action_url': n.action_url or '',
    }
