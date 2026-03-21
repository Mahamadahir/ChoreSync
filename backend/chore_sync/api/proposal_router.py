"""DRF views for task proposal and voting endpoints."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from chore_sync.services.proposal_service import ProposalService

_svc = ProposalService()


class GroupProposalListCreateAPIView(APIView):
    """
    GET  /api/groups/{pk}/proposals/ — list proposals for a group
    POST /api/groups/{pk}/proposals/ — create a new proposal
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
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
        task_template_id = request.data.get('task_template_id')
        if not task_template_id:
            return Response(
                {'detail': 'task_template_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            task_template_id = int(task_template_id)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'task_template_id must be an integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            proposal = _svc.create_proposal(
                proposer_id=str(request.user.id),
                group_id=str(pk),
                task_template_id=task_template_id,
                reason=request.data.get('reason', ''),
            )
        except PermissionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(_serialize(proposal), status=status.HTTP_201_CREATED)


class ProposalVoteAPIView(APIView):
    """POST /api/proposals/{pk}/vote/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        choice = request.data.get('choice')
        if not choice:
            return Response(
                {'detail': 'choice is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            proposal = _svc.cast_vote(
                proposal_id=int(pk),
                voter_id=str(request.user.id),
                choice=choice,
                note=request.data.get('note', ''),
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
    votes = list(p.votes.all())
    support = sum(1 for v in votes if v.choice == 'support')
    reject = sum(1 for v in votes if v.choice == 'reject')
    abstain = sum(1 for v in votes if v.choice == 'abstain')
    return {
        'id': p.id,
        'state': p.state,
        'reason': p.reason,
        'voting_deadline': p.voting_deadline.isoformat() if p.voting_deadline else None,
        'required_support_ratio': p.required_support_ratio,
        'approved_at': p.approved_at.isoformat() if p.approved_at else None,
        'created_at': p.created_at.isoformat(),
        'proposed_by': p.proposed_by.username if p.proposed_by else None,
        'task_template_id': p.task_template_id,
        'task_template_name': p.task_template.name if p.task_template else None,
        'votes': {'support': support, 'reject': reject, 'abstain': abstain},
    }
