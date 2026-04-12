"""DRF views for task suggestion and moderator approval endpoints."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from chore_sync.services.proposal_service import ProposalService

_svc = ProposalService()


class GroupProposalListCreateAPIView(APIView):
    """
    GET  /api/groups/{pk}/proposals/ — list proposals for a group
    POST /api/groups/{pk}/proposals/ — submit a task suggestion
    """
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            proposals = _svc.list_proposals(
                group_id=str(pk),
                actor_id=str(request.user.id),
            )
        except PermissionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response([_serialize(p) for p in proposals])

    def post(self, request, pk):
        payload = request.data.get('payload')
        if not payload or not isinstance(payload, dict):
            return Response(
                {'detail': 'payload is required and must be an object.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            proposal = _svc.create_proposal(
                proposer_id=str(request.user.id),
                group_id=str(pk),
                payload=payload,
                reason=request.data.get('reason', ''),
            )
        except PermissionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(_serialize(proposal), status=status.HTTP_201_CREATED)


class ProposalApproveAPIView(APIView):
    """POST /api/proposals/{pk}/approve/ — moderator approves, optionally editing fields"""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        edited_payload = request.data.get('edited_payload')  # dict or null
        approval_note = request.data.get('approval_note', '')

        try:
            proposal = _svc.approve(
                proposal_id=int(pk),
                moderator_id=str(request.user.id),
                edited_payload=edited_payload if isinstance(edited_payload, dict) else None,
                approval_note=approval_note,
            )
        except PermissionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(_serialize(proposal))


class ProposalRejectAPIView(APIView):
    """POST /api/proposals/{pk}/reject/ — moderator rejects with a note"""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        note = request.data.get('note', '')
        try:
            proposal = _svc.reject(
                proposal_id=int(pk),
                moderator_id=str(request.user.id),
                note=note,
            )
        except PermissionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(_serialize(proposal))


# ------------------------------------------------------------------ #
#  Serialiser helper
# ------------------------------------------------------------------ #

def _serialize(p) -> dict:
    return {
        'id': p.id,
        'state': p.state,
        'reason': p.reason,
        'proposed_payload': p.proposed_payload,
        'approved_payload': p.approved_payload,
        'payload_diff': p.payload_diff,
        'approval_note': p.approval_note,
        'approved_at': p.approved_at.isoformat() if p.approved_at else None,
        'approved_by': p.approved_by.username if p.approved_by else None,
        'created_at': p.created_at.isoformat(),
        'proposed_by': p.proposed_by.username if p.proposed_by else None,
        'proposed_by_id': str(p.proposed_by_id) if p.proposed_by_id else None,
        'task_template_id': p.task_template_id,
        'task_template_name': p.task_template.name if p.task_template else None,
    }
