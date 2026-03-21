"""Proposal and voting service for ChoreSync."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from chore_sync.models import GroupMembership, TaskProposal, TaskTemplate, TaskVote


@dataclass
class ProposalService:
    """Handles task proposal creation and vote tallying."""

    # ------------------------------------------------------------------ #
    #  Create
    # ------------------------------------------------------------------ #

    def create_proposal(
        self,
        *,
        proposer_id: str,
        group_id: str,
        task_template_id: int,
        reason: str = '',
    ) -> TaskProposal:
        """Create a task proposal and notify all group members.

        Inputs:
            proposer_id: Must be a group member.
            group_id: Target group.
            task_template_id: The TaskTemplate being proposed.
            reason: Optional explanation.
        Output:
            Created TaskProposal.
        """
        if not GroupMembership.objects.filter(
            user_id=proposer_id, group_id=group_id
        ).exists():
            raise PermissionError('You are not a member of this group.')

        if not TaskTemplate.objects.filter(id=task_template_id, group_id=group_id).exists():
            raise ValueError('Task template not found in this group.')

        proposal = TaskProposal.objects.create(
            proposed_by_id=proposer_id,
            group_id=group_id,
            task_template_id=task_template_id,
            reason=reason,
            voting_deadline=timezone.now() + timedelta(hours=72),
        )

        self._notify_members(proposal=proposal, group_id=group_id, proposer_id=proposer_id)
        return proposal

    # ------------------------------------------------------------------ #
    #  Vote
    # ------------------------------------------------------------------ #

    def cast_vote(
        self,
        *,
        proposal_id: int,
        voter_id: str,
        choice: str,
        note: str = '',
    ) -> TaskProposal:
        """Record or update a vote, then evaluate the proposal outcome.

        Inputs:
            proposal_id: Target proposal (must be pending).
            voter_id: Must be a group member.
            choice: 'support' | 'reject' | 'abstain'.
        Output:
            Updated TaskProposal.
        """
        proposal = TaskProposal.objects.select_related('group', 'task_template').filter(
            id=proposal_id
        ).first()
        if proposal is None:
            raise ValueError('Proposal not found.')
        if not proposal.is_open:
            raise ValueError('This proposal is no longer open for voting.')
        if not GroupMembership.objects.filter(
            user_id=voter_id, group_id=proposal.group_id
        ).exists():
            raise PermissionError('You are not a member of this group.')
        if choice not in ('support', 'reject', 'abstain'):
            raise ValueError("choice must be 'support', 'reject', or 'abstain'.")

        TaskVote.objects.update_or_create(
            proposal=proposal,
            voter_id=voter_id,
            defaults={'choice': choice, 'note': note},
        )

        self._evaluate(proposal)
        proposal.refresh_from_db()
        return proposal

    # ------------------------------------------------------------------ #
    #  List
    # ------------------------------------------------------------------ #

    def list_proposals(self, *, group_id: str, actor_id: str) -> list[TaskProposal]:
        """Return all proposals for a group, ordered newest first."""
        if not GroupMembership.objects.filter(
            user_id=actor_id, group_id=group_id
        ).exists():
            raise PermissionError('You are not a member of this group.')

        return list(
            TaskProposal.objects.filter(group_id=group_id)
            .select_related('proposed_by', 'task_template')
            .prefetch_related('votes')
            .order_by('-created_at')
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _evaluate(self, proposal: TaskProposal) -> None:
        """Resolve proposal if all members have voted or the deadline has passed."""
        with transaction.atomic():
            # Lock the row so concurrent calls don't double-resolve
            locked = (
                TaskProposal.objects.select_related('task_template')
                .select_for_update()
                .filter(id=proposal.id, state='pending')
                .first()
            )
            if locked is None:
                return  # Already resolved by a concurrent call

            member_count = GroupMembership.objects.filter(
                group_id=locked.group_id
            ).count()
            vote_count = TaskVote.objects.filter(proposal=locked).count()

            deadline_passed = (
                locked.voting_deadline and timezone.now() >= locked.voting_deadline
            )
            all_voted = vote_count >= member_count

            if not (all_voted or deadline_passed):
                return

            support = TaskVote.objects.filter(proposal=locked, choice='support').count()
            reject = TaskVote.objects.filter(proposal=locked, choice='reject').count()
            decisive = support + reject

            # Everyone abstained → treat as rejected
            support_ratio = support / decisive if decisive > 0 else 0.0

            if support_ratio >= locked.required_support_ratio:
                locked.state = 'approved'
                locked.approved_at = timezone.now()
                locked.save(update_fields=['state', 'approved_at'])
                if locked.task_template:
                    locked.task_template.active = True
                    locked.task_template.save(update_fields=['active'])
            else:
                locked.state = 'rejected'
                locked.save(update_fields=['state'])

    def _notify_members(
        self, *, proposal: TaskProposal, group_id: str, proposer_id: str
    ) -> None:
        """Notify every group member except the proposer of the new proposal."""
        from chore_sync.services.notification_service import NotificationService

        nsvc = NotificationService()
        template_name = (
            proposal.task_template.name if proposal.task_template else 'a task'
        )
        member_ids = (
            GroupMembership.objects.filter(group_id=group_id)
            .exclude(user_id=proposer_id)
            .values_list('user_id', flat=True)
        )
        for uid in member_ids:
            nsvc.emit_notification(
                recipient_id=str(uid),
                notification_type='task_proposal',
                title=f'New proposal: {template_name}',
                content=(
                    f'A new task "{template_name}" has been proposed. '
                    f'Cast your vote before the deadline.'
                ),
                group_id=group_id,
                task_proposal_id=proposal.id,
            )
