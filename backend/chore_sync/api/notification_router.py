"""DRF views for notification endpoints."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from chore_sync.services.notification_service import NotificationService

_svc = NotificationService()


class NotificationListAPIView(APIView):
    """GET /api/notifications/ — return active (non-dismissed) notifications."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        since_id = request.query_params.get('since_id')
        if since_id and since_id.isdigit():
            notifications = _svc.list_notifications_since(
                recipient_id=str(request.user.id),
                since_id=int(since_id),
            )
        else:
            notifications = _svc.list_active_notifications(
                recipient_id=str(request.user.id)
            )
        return Response([_serialize(n) for n in notifications])


class NotificationHistoryAPIView(APIView):
    """GET /api/notifications/history/ — paginated full history."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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


class NotificationReadAllAPIView(APIView):
    """POST /api/notifications/read-all/ — mark every unread notification as read."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = _svc.mark_all_read(actor_id=str(request.user.id))
        return Response({'marked_read': count})


class NotificationDismissAPIView(APIView):
    """POST /api/notifications/{pk}/dismiss/ — dismiss a notification."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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


class NotificationPreferenceAPIView(APIView):
    """GET/PATCH /api/users/me/notification-preferences/"""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    _BOOLEAN_FIELDS = [
        'deadline_reminders', 'task_assigned', 'task_swap',
        'emergency_reassign', 'badge_earned', 'marketplace_activity',
        'smart_suggestions', 'quiet_hours_enabled',
    ]
    _TIME_FIELDS = ['quiet_start', 'quiet_end']

    def get(self, request):
        from chore_sync.models import NotificationPreference
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return Response(_serialize_prefs(prefs))

    def patch(self, request):
        from chore_sync.models import NotificationPreference
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        data = request.data
        update_fields = []

        for field in self._BOOLEAN_FIELDS:
            if field in data:
                setattr(prefs, field, bool(data[field]))
                update_fields.append(field)

        for field in self._TIME_FIELDS:
            if field in data:
                raw = data[field]
                if raw is None or raw == '':
                    setattr(prefs, field, None)
                else:
                    # Accept "HH:MM" or "HH:MM:SS"
                    from datetime import time as dtime
                    parts = str(raw).split(':')
                    try:
                        h, m = int(parts[0]), int(parts[1])
                        setattr(prefs, field, dtime(h, m))
                    except (IndexError, ValueError):
                        return Response(
                            {'detail': f'Invalid time format for {field}. Use HH:MM.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                update_fields.append(field)

        if update_fields:
            prefs.save(update_fields=update_fields)
        return Response(_serialize_prefs(prefs))


# ------------------------------------------------------------------ #
#  Serialiser helper
# ------------------------------------------------------------------ #

def _serialize_prefs(p) -> dict:
    return {
        'deadline_reminders':   p.deadline_reminders,
        'task_assigned':        p.task_assigned,
        'task_swap':            p.task_swap,
        'emergency_reassign':   p.emergency_reassign,
        'badge_earned':         p.badge_earned,
        'marketplace_activity': p.marketplace_activity,
        'smart_suggestions':    p.smart_suggestions,
        'quiet_hours_enabled':  p.quiet_hours_enabled,
        'quiet_start':          p.quiet_start.strftime('%H:%M') if p.quiet_start else None,
        'quiet_end':            p.quiet_end.strftime('%H:%M') if p.quiet_end else None,
    }


class PushTokenAPIView(APIView):
    """POST /api/push-token/ — register or refresh an Expo push token for the current user."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from chore_sync.models import UserPushToken
        token = request.data.get('token', '').strip()
        platform = request.data.get('platform', 'ios')
        if not token:
            return Response({'detail': 'token is required.'}, status=400)
        if platform not in ('ios', 'android'):
            platform = 'ios'
        # Upsert: if token exists for another user, re-assign; otherwise create/update
        UserPushToken.objects.update_or_create(
            token=token,
            defaults={'user_id': request.user.id, 'platform': platform},
        )
        return Response({'status': 'registered'})

    def delete(self, request):
        """DELETE /api/push-token/ — deregister the token (e.g. on logout)."""
        from chore_sync.models import UserPushToken
        token = request.data.get('token', '').strip()
        if token:
            UserPushToken.objects.filter(user=request.user, token=token).delete()
        return Response(status=204)


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
        'task_swap_id': n.task_swap_id,
        'task_proposal_id': n.task_proposal_id,
        'message_id': n.message_id,
        'action_url': n.action_url or '',
    }
