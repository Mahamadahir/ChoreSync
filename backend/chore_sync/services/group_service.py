"""Group management services for ChoreSync."""
from __future__ import annotations
from dataclasses import dataclass
from django.db import transaction
from django.conf import settings
import secrets
from chore_sync.models import Group, User, GroupMembership,Notification, GroupCalendar
from chore_sync.services.auth_service import AccountService


@dataclass
class GroupOrchestrator:
    """Handles group lifecycle, membership, and assignment configuration."""

    def create_group(self, *, owner: User, name: str, reassignment_rule: str | None = None, fairness_algorithm: str | None = None) -> Group:
        """Provision a new group and default configuration.

        Inputs:
            owner: User creating the group (initial admin).
            name: Human-friendly group name.
            reassignment_rule: Initial fairness/rotation setting identifier.
            fairness_algorithm: Algorithm for computing task fairness.
        Output:
            Group DTO (id, slug, invite code) ready for UI consumption.
        TODO: Persist the Group + owner membership transactionally, seed default task templates,
        TODO: provision in-app calendars/message threads, and emit onboarding events.
        """
        valid_rules = [c[0] for c in Group._meta.get_field('reassignment_rule').choices]
        valid_algorithms = [c[0] for c in Group._meta.get_field('fairness_algorithm').choices]
        if name is None or len(name) == 0:
            raise ValueError("Group name cannot be empty.")
        if len(name) > 100:
            raise ValueError("Group name cannot exceed 100 characters.")

        if reassignment_rule is not None and reassignment_rule not in valid_rules:
            raise ValueError(f"Invalid reassignment rule: {reassignment_rule}")
        if fairness_algorithm is not None and fairness_algorithm not in valid_algorithms:
            raise ValueError(f"Invalid fairness algorithm: {fairness_algorithm}")

        with transaction.atomic():
            group = Group.objects.create(name=name, owner=owner, reassignment_rule=reassignment_rule, group_code=secrets.token_urlsafe(6).upper(), fairness_algorithm=fairness_algorithm)
            GroupMembership.objects.create(user=owner, group=group, role='moderator')
            GroupCalendar.objects.create(group=group)
        return group

    def invite_member(self, *, requestor: User, invitee: User, group_id: str, email: str, role: str) -> None:
        """Send an invitation email and pre-stage membership for first login.

        Inputs:
            requestor: User sending the invitation.
            invitee: User being invited.
            group_id: Target group.
            email: Invitee email address.
        Output:
            None. Should return invite metadata or raise if the invite cannot be issued.
        TODO: Generate expiring tokens, upsert pending Membership rows, queue transactional email/SMS,
        TODO: and log invite analytics for later redemption tracking.
        """

        group = Group.objects.filter(id=group_id).first()
        if group is None:
            raise ValueError("Group not found.")
        group_membership = group.members.filter(user=requestor).first()
        if group.members.filter(user=invitee).exists():
            raise ValueError("User is already a member of the group.")
        if group_membership is None:
            raise ValueError("Requestor must be a member of the group to invite others.")
        if group_membership.role != 'moderator':
            raise ValueError("Requestor must be a moderator to invite others.")
        if role not in ['member', 'moderator']:
            raise ValueError("Invalid role specified for invitee.")

        with transaction.atomic():
            GroupMembership.objects.create(user=invitee, group=group, role=role)
            Notification.objects.create(title="Group Invitation", type='group_invite', recipient=invitee, group=group, content=f"You have been invited to join the group '{group.name}' as a {role}.")

        svc = AccountService()
        svc._send_and_log_email(
            to_address=invitee.email,
            subject=f"You're invited to join {group.name} on ChoreSync!",
            message=(
                f"Hi {invitee.first_name},\n\n"
                f"{requestor.first_name} has invited you to join the group '{group.name}' on ChoreSync as a {role}.\n"
                f"Use this code to join: {group.group_code}\n\n"
                f"Or sign up at {settings.FRONTEND_APP_URL}/join/{group.group_code}"
            ),
            context={"type": "group_invite", "group_id": str(group.id)},
        )

    def compute_assignment_matrix(self, *, group_id: str) -> None:
        """Build a fairness matrix used for automated task assignments.

        Inputs:
            group_id: Group whose workload distribution is being analyzed.
        Output:
            Matrix object keyed by member/task type with weights or raises if data insufficient.
        TODO: Aggregate historical completions, normalize workload metrics, incorporate preferences,
        TODO: output scores consumable by TaskScheduler for upcoming rotations.
        """
        raise NotImplementedError("TODO: implement load balancing matrix computation")

    def generate_invite_code(self, *, length: int = 6) -> None:
        """Produce a human-friendly invite code for group onboarding.

        Inputs:
            length: Desired code length (default 6).
        Output:
            Randomized, collision-resistant invite code string reserved for later redemption.
        TODO: Generate secure codes, ensure uniqueness scoped per group, persist reservations with
        TODO: expiry metadata, and expose them via membership onboarding flows.
        """
        raise NotImplementedError("TODO: implement invite code generation")
