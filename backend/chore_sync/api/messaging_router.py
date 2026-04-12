"""REST endpoint for group chat message history and read receipts."""
from __future__ import annotations

from collections import defaultdict

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from chore_sync.models import GroupMembership, Message, MessageReceipt


class GroupMessageListAPIView(APIView):
    """GET /api/groups/<pk>/messages/ — paginated message history."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not GroupMembership.objects.filter(user=request.user, group_id=pk).exists():
            return Response({'detail': 'Not a member of this group.'}, status=403)

        try:
            limit = max(1, min(100, int(request.query_params.get('limit', 50))))
        except (ValueError, TypeError):
            limit = 50

        before_id = request.query_params.get('before')
        qs = Message.objects.filter(group_id=pk).select_related('sender')
        if before_id:
            qs = qs.filter(id__lt=before_id)

        messages = list(qs.order_by('-id')[:limit])
        messages.reverse()

        msg_ids = [m.id for m in messages]

        # Fetch all receipts for these messages (excluding viewer's own receipts)
        receipts = (
            MessageReceipt.objects
            .filter(message_id__in=msg_ids, seen_at__isnull=False)
            .exclude(user=request.user)
            .select_related('user')
        )
        receipt_map: dict[int, list[dict]] = defaultdict(list)
        for r in receipts:
            receipt_map[r.message_id].append({
                'user_id': str(r.user_id),
                'username': r.user.username,
                'seen_at': r.seen_at.isoformat(),
            })

        # Total members — used to decide whether all_read is True
        total_members = GroupMembership.objects.filter(group_id=pk).count()

        return Response([
            _serialize(m, read_by=receipt_map[m.id], total_members=total_members)
            for m in messages
        ])


class MarkReadAPIView(APIView):
    """POST /api/groups/<pk>/messages/read/ — mark messages as seen."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not GroupMembership.objects.filter(user=request.user, group_id=pk).exists():
            return Response({'detail': 'Not a member of this group.'}, status=403)

        message_ids = request.data.get('message_ids', [])
        if not isinstance(message_ids, list):
            return Response({'detail': 'message_ids must be a list.'}, status=400)

        valid_ids = Message.objects.filter(
            id__in=message_ids, group_id=pk
        ).values_list('id', flat=True)

        now = timezone.now()
        for mid in valid_ids:
            MessageReceipt.objects.update_or_create(
                message_id=mid,
                user=request.user,
                defaults={'seen_at': now},
            )

        return Response(status=204)


def _serialize(m: Message, read_by: list | None = None, total_members: int = 0) -> dict:
    readers = read_by or []
    # all_read: every non-sender member has a receipt (need at least 1 other member)
    non_sender_members = max(total_members - 1, 0)
    all_read = non_sender_members > 0 and len(readers) >= non_sender_members
    return {
        'id': m.id,
        'group_id': str(m.group_id),
        'sender_id': str(m.sender_id) if m.sender_id else None,
        'username': m.sender.username if m.sender else 'Unknown',
        'body': m.content,
        'sent_at': m.timestamp.isoformat(),
        'read_by': readers,
        'all_read': all_read,
    }
