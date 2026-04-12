"""Proposal and approval service for ChoreSync.

Replaces the voting model with a simple moderator approve/reject flow.
Members submit task suggestions (with full task details); any moderator
can approve (optionally editing the details first) or reject with a note.
The proposed_payload is frozen at submission; approved_payload records
any moderator edits, making the diff a built-in audit log.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from chore_sync.models import GroupMembership, TaskProposal, TaskTemplate


@dataclass
class ProposalService:

    # ------------------------------------------------------------------ #
    #  Submit suggestion
    # ------------------------------------------------------------------ #

    def create_proposal(
        self,
        *,
        proposer_id: str,
        group_id: str,
        payload: dict,
        reason: str = '',
    ) -> TaskProposal:
        """Submit a task suggestion for moderator review.

        Inputs:
            proposer_id: Must be a group member.
            group_id: Target group.
            payload: Full task details — required keys: name, next_due.
                     Optional: category, difficulty, estimated_mins,
                     recurring_choice, recur_value, days_of_week, details.
            reason: Optional explanation from the proposer.
        Output:
            Created TaskProposal in 'pending' state.
        """
        if not GroupMembership.objects.filter(
            user_id=proposer_id, group_id=group_id
        ).exists():
            raise PermissionError('You are not a member of this group.')

        if not payload.get('name'):
            raise ValueError('Task name is required.')
        if not payload.get('next_due'):
            raise ValueError('Start date (next_due) is required.')

        # Freeze a clean copy — strip unknown keys defensively
        allowed_keys = {
            'name', 'category', 'difficulty', 'estimated_mins',
            'recurring_choice', 'recur_value', 'days_of_week',
            'next_due', 'details', 'importance',
        }
        clean_payload = {k: v for k, v in payload.items() if k in allowed_keys}
        clean_payload.setdefault('category', 'other')
        clean_payload.setdefault('difficulty', 1)
        clean_payload.setdefault('estimated_mins', 30)
        clean_payload.setdefault('recurring_choice', 'none')
        clean_payload.setdefault('importance', 'core')

        proposal = TaskProposal.objects.create(
            proposed_by_id=proposer_id,
            group_id=group_id,
            proposed_payload=clean_payload,
            reason=reason,
        )

        self._notify_moderators(proposal=proposal, group_id=group_id, proposer_id=proposer_id)
        return proposal

    # ------------------------------------------------------------------ #
    #  Approve
    # ------------------------------------------------------------------ #

    def approve(
        self,
        *,
        proposal_id: int,
        moderator_id: str,
        edited_payload: dict | None = None,
        approval_note: str = '',
    ) -> TaskProposal:
        """Approve a pending proposal, optionally editing the task details.

        Inputs:
            proposal_id: Target TaskProposal (must be pending).
            moderator_id: Must be a group moderator.
            edited_payload: Partial or full override of proposed_payload.
                            Only differing fields need to be included.
                            If None, the proposal is approved as-is.
            approval_note: Optional explanation for any edits.
        Output:
            Updated TaskProposal with state='approved' and task_template set.
        """
        with transaction.atomic():
            proposal = (
                TaskProposal.objects.select_related('group')
                .select_for_update(of=('self',))
                .filter(id=proposal_id)
                .first()
            )
            if proposal is None:
                raise ValueError('Proposal not found.')
            if not proposal.is_open:
                raise ValueError('This proposal is no longer pending.')

            self._require_moderator(moderator_id=moderator_id, group_id=str(proposal.group_id))

            # Build the effective payload
            if edited_payload:
                # Merge: start from proposed, overlay moderator edits
                merged = dict(proposal.proposed_payload)
                allowed_keys = {
                    'name', 'category', 'difficulty', 'estimated_mins',
                    'recurring_choice', 'recur_value', 'days_of_week',
                    'next_due', 'details', 'importance',
                }
                for k, v in edited_payload.items():
                    if k in allowed_keys:
                        merged[k] = v
                # Only store approved_payload if something actually changed
                proposal.approved_payload = merged if merged != proposal.proposed_payload else None
            else:
                proposal.approved_payload = None

            effective = proposal.approved_payload or proposal.proposed_payload

            # Create the TaskTemplate
            from django.utils.dateparse import parse_datetime
            next_due = effective.get('next_due')
            if isinstance(next_due, str):
                next_due = parse_datetime(next_due)

            template = TaskTemplate.objects.create(
                name=effective['name'],
                category=effective.get('category', 'other'),
                difficulty=effective.get('difficulty', 1),
                estimated_mins=effective.get('estimated_mins', 30),
                recurring_choice=effective.get('recurring_choice', 'none'),
                recur_value=effective.get('recur_value'),
                days_of_week=effective.get('days_of_week'),
                next_due=next_due,
                details=effective.get('details', ''),
                importance=effective.get('importance', 'core'),
                creator_id=proposal.proposed_by_id,
                group=proposal.group,
                active=True,
            )

            proposal.task_template = template
            proposal.state = 'approved'
            proposal.approved_by_id = moderator_id
            proposal.approved_at = timezone.now()
            proposal.approval_note = approval_note
            proposal.save(update_fields=[
                'task_template', 'state', 'approved_by_id',
                'approved_at', 'approved_payload', 'approval_note',
            ])

        # Spawn the first occurrence immediately (outside the lock so the
        # assignment pipeline can run without holding the proposal row lock).
        from chore_sync.services.task_lifecycle_service import TaskLifecycleService
        try:
            TaskLifecycleService().generate_recurring_instances(
                task_template_id=str(template.id)
            )
        except Exception:
            pass  # Celery beat will pick it up on the next tick if this fails

        self._notify_proposer_approved(proposal)
        return proposal

    # ------------------------------------------------------------------ #
    #  Reject
    # ------------------------------------------------------------------ #

    def reject(
        self,
        *,
        proposal_id: int,
        moderator_id: str,
        note: str = '',
    ) -> TaskProposal:
        """Reject a pending proposal.

        Inputs:
            proposal_id: Target TaskProposal (must be pending).
            moderator_id: Must be a group moderator.
            note: Required explanation for the rejection.
        Output:
            Updated TaskProposal with state='rejected'.
        """
        with transaction.atomic():
            proposal = (
                TaskProposal.objects.select_related('group')
                .select_for_update(of=('self',))
                .filter(id=proposal_id)
                .first()
            )
            if proposal is None:
                raise ValueError('Proposal not found.')
            if not proposal.is_open:
                raise ValueError('This proposal is no longer pending.')

            self._require_moderator(moderator_id=moderator_id, group_id=str(proposal.group_id))

            proposal.state = 'rejected'
            proposal.approved_by_id = moderator_id
            proposal.approval_note = note
            proposal.save(update_fields=['state', 'approved_by_id', 'approval_note'])

            self._notify_proposer_rejected(proposal)
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
            .select_related('proposed_by', 'task_template', 'approved_by')
            .order_by('-created_at')
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _require_moderator(*, moderator_id: str, group_id: str) -> None:
        membership = GroupMembership.objects.filter(
            user_id=moderator_id, group_id=group_id
        ).first()
        if membership is None:
            raise PermissionError('You are not a member of this group.')
        if membership.role != 'moderator':
            raise PermissionError('Only moderators can approve or reject proposals.')

    def _notify_moderators(
        self, *, proposal: TaskProposal, group_id: str, proposer_id: str
    ) -> None:
        from chore_sync.services.notification_service import NotificationService
        nsvc = NotificationService()
        task_name = proposal.proposed_payload.get('name', 'a task')
        moderator_ids = (
            GroupMembership.objects.filter(group_id=group_id, role='moderator')
            .exclude(user_id=proposer_id)
            .values_list('user_id', flat=True)
        )
        for uid in moderator_ids:
            nsvc.emit_notification(
                recipient_id=str(uid),
                notification_type='task_proposal',
                title=f'New suggestion: {task_name}',
                content=(
                    f'A member has suggested adding "{task_name}". '
                    f'Review and approve or reject it.'
                ),
                group_id=group_id,
                task_proposal_id=proposal.id,
                action_url=f'/groups/{group_id}?tab=discover',
            )

    def _notify_proposer_approved(self, proposal: TaskProposal) -> None:
        if not proposal.proposed_by_id:
            return
        from chore_sync.services.notification_service import NotificationService
        nsvc = NotificationService()
        task_name = proposal.proposed_payload.get('name', 'Your task')
        content = f'"{task_name}" has been approved and added to the group.'
        if proposal.payload_diff:
            changes = ', '.join(proposal.payload_diff.keys())
            content += f' Note: {proposal.approved_by} adjusted: {changes}.'
        if proposal.approval_note:
            content += f' "{proposal.approval_note}"'
        nsvc.emit_notification(
            recipient_id=str(proposal.proposed_by_id),
            notification_type='task_proposal',
            title=f'Suggestion approved: {task_name}',
            content=content,
            group_id=str(proposal.group_id),
            task_proposal_id=proposal.id,
            action_url=f'/groups/{proposal.group_id}?tab=discover',
        )

    def _notify_proposer_rejected(self, proposal: TaskProposal) -> None:
        if not proposal.proposed_by_id:
            return
        from chore_sync.services.notification_service import NotificationService
        nsvc = NotificationService()
        task_name = proposal.proposed_payload.get('name', 'Your suggestion')
        content = f'"{task_name}" was not approved.'
        if proposal.approval_note:
            content += f' Reason: {proposal.approval_note}'
        nsvc.emit_notification(
            recipient_id=str(proposal.proposed_by_id),
            notification_type='task_proposal',
            title=f'Suggestion declined: {task_name}',
            content=content,
            group_id=str(proposal.group_id),
            task_proposal_id=proposal.id,
            action_url=f'/groups/{proposal.group_id}?tab=discover',
        )
