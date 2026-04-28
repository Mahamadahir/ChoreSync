"""DRF views for task suggestion, moderator approval, and group-vote endpoints."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from chore_sync.services.proposal_service import ProposalService

_svc = ProposalService()

AUTH = [CsrfExemptSessionAuthentication, JWTAuthentication]


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
        return Response([_serialize(p, request.user.id) for p in proposals])

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
                vote_mode=bool(request.data.get('vote_mode', False)),
            )
        except PermissionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(_serialize(proposal, request.user.id), status=status.HTTP_201_CREATED)


class ProposalApproveAPIView(APIView):
    """POST /api/proposals/{pk}/approve/ — moderator approves, optionally editing fields"""
    authentication_classes = AUTH
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

        return Response(_serialize(proposal, request.user.id))


class ProposalRejectAPIView(APIView):
    """POST /api/proposals/{pk}/reject/ — moderator rejects with a note"""
    authentication_classes = AUTH
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

        return Response(_serialize(proposal, request.user.id))


class ProposalVoteAPIView(APIView):
    """
    POST   /api/proposals/{pk}/vote/  — cast or update a vote
    DELETE /api/proposals/{pk}/vote/  — retract a vote
    """
    authentication_classes = AUTH
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        choice = request.data.get('choice', '')
        try:
            vote = _svc.cast_vote(
                proposal_id=int(pk),
                voter_id=str(request.user.id),
                choice=choice,
            )
        except PermissionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Return the updated proposal so the client can refresh in one round-trip
        from chore_sync.models import TaskProposal
        proposal = TaskProposal.objects.select_related(
            'proposed_by', 'approved_by', 'task_template'
        ).get(id=pk)
        return Response(_serialize(proposal, request.user.id))

    def delete(self, request, pk):
        try:
            _svc.retract_vote(proposal_id=int(pk), voter_id=str(request.user.id))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        from chore_sync.models import TaskProposal
        proposal = TaskProposal.objects.select_related(
            'proposed_by', 'approved_by', 'task_template'
        ).get(id=pk)
        return Response(_serialize(proposal, request.user.id))


# ------------------------------------------------------------------ #
#  Serialiser helper
# ------------------------------------------------------------------ #

def _serialize(p, viewer_id=None) -> dict:
    from django.utils import timezone
    from chore_sync.models import TaskVote

    # Vote counts — only revealed once the window is closed (blind voting)
    vote_data: dict = {
        'vote_mode': p.vote_mode,
        'vote_deadline': p.vote_deadline.isoformat() if p.vote_deadline else None,
        'is_vote_open': p.is_vote_open if p.vote_mode else False,
        'my_vote': None,
        'vote_counts': None,
    }
    if p.vote_mode:
        votes_qs = TaskVote.objects.filter(proposal=p)
        # Reveal tally only once the vote is closed
        if not p.is_vote_open:
            votes = list(votes_qs.values_list('choice', flat=True))
            vote_data['vote_counts'] = {
                'yes': votes.count('yes'),
                'no': votes.count('no'),
                'abstain': votes.count('abstain'),
                'total': len(votes),
            }
        # Always show the viewer's own vote
        if viewer_id:
            own = votes_qs.filter(voter_id=viewer_id).values_list('choice', flat=True).first()
            vote_data['my_vote'] = own

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
        **vote_data,
    }
