"""Group invitation endpoints — list pending invitations, accept or decline."""

from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.models import GroupInvitation, GroupMembership


class InvitationListAPIView(APIView):
    """GET /api/invitations/ — list pending invitations for the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        invitations = (
            GroupInvitation.objects
            .filter(invitee=request.user, status='pending')
            .select_related('group', 'invited_by')
            .order_by('-created_at')
        )
        return Response([
            {
                'id': inv.id,
                'group_id': str(inv.group.id),
                'group_name': inv.group.name,
                'invited_by': inv.invited_by.username if inv.invited_by else None,
                'role': inv.role,
                'created_at': inv.created_at.isoformat(),
            }
            for inv in invitations
        ])


class InvitationRespondAPIView(APIView):
    """POST /api/invitations/<pk>/accept/  — accept a pending invitation.
       POST /api/invitations/<pk>/decline/ — decline a pending invitation."""
    permission_classes = [IsAuthenticated]

    def _get_invitation(self, pk, user):
        inv = GroupInvitation.objects.select_related('group').filter(
            pk=pk, invitee=user, status='pending',
        ).first()
        if inv is None:
            return None, Response({'detail': 'Invitation not found or already resolved.'}, status=404)
        return inv, None

    def post(self, request, pk, action):
        inv, err = self._get_invitation(pk, request.user)
        if err:
            return err

        if action == 'accept':
            with transaction.atomic():
                if inv.group.members.filter(user=request.user).exists():
                    inv.status = 'accepted'
                    inv.save(update_fields=['status'])
                    return Response({'detail': 'You are already a member of this group.'})
                GroupMembership.objects.create(user=request.user, group=inv.group, role=inv.role)
                inv.status = 'accepted'
                inv.save(update_fields=['status'])
            return Response({'detail': f"You've joined {inv.group.name}.", 'group_id': str(inv.group.id)})

        if action == 'decline':
            inv.status = 'declined'
            inv.save(update_fields=['status'])
            return Response({'detail': 'Invitation declined.'})

        return Response({'detail': 'Invalid action.'}, status=400)
