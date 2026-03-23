"""Group management services for ChoreSync."""
from __future__ import annotations
from dataclasses import dataclass
from django.db import transaction
from django.conf import settings
import secrets
from chore_sync.models import Group, User, GroupMembership, Notification, GroupCalendar, UserStats, TaskOccurrence
from chore_sync.services.auth_service import AccountService


@dataclass
class GroupOrchestrator:
    """Handles group lifecycle, membership, and assignment configuration."""

    @staticmethod
    def _normalise(matrix: dict[str, float]) -> dict[str, float]:
        if not matrix:
            raise ValueError("Cannot normalise an empty matrix - group has no members")

        values = list(matrix.values())
        min_val = min(values)
        max_val = max(values)

        if max_val == min_val:
            return {uid: 0.0 for uid in matrix}

        return {
            uid: (score - min_val) / (max_val - min_val)
            for uid, score in matrix.items()
        }


    def create_group(self, *, owner: User, name: str, reassignment_rule: str | None = None, fairness_algorithm: str | None = None) -> Group:
        """Provision a new group and default configuration.

        Inputs:
            owner: User creating the group (initial admin).
            name: Human-friendly group name.
            reassignment_rule: Initial fairness/rotation setting identifier.
            fairness_algorithm: Algorithm for computing task fairness.
        Output:
            Group DTO (id, slug, invite code) ready for UI consumption.
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

    def invite_member(self, *, requestor: User, group_id: str, email: str, role: str) -> None:
        """Send an invitation email and create membership if the invitee already has an account.

        Inputs:
            requestor: User sending the invitation (must be a group moderator).
            group_id: Target group UUID (str).
            email: Email address of the person being invited.
            role: Role to assign — 'member' or 'moderator'.
        Output:
            None. Raises ValueError for any validation failure.

        Behaviour:
            - Existing user: creates GroupMembership immediately + in-app Notification + email.
            - Unknown email: sends email with group_code for self-join after signup.
        """
        group = Group.objects.filter(id=group_id).first()
        if group is None:
            raise ValueError("Group not found.")

        requestor_membership = group.members.filter(user=requestor).first()
        if requestor_membership is None:
            raise ValueError("Requestor must be a member of the group to invite others.")
        if requestor_membership.role != 'moderator':
            raise ValueError("Requestor must be a moderator to invite others.")

        invitee = User.objects.filter(email=email).first()

        if invitee is not None:
            if group.members.filter(user=invitee).exists():
                raise ValueError("User is already a member of the group.")
            with transaction.atomic():
                GroupMembership.objects.create(user=invitee, group=group, role=role)
                Notification.objects.create(
                    title="Group Invitation",
                    type='group_invite',
                    recipient=invitee,
                    group=group,
                    content=f"You have been invited to join the group '{group.name}' as a {role}.",
                )
            AccountService()._send_and_log_email(
                to_address=invitee.email,
                subject=f"You're invited to join {group.name} on ChoreSync!",
                message=(
                    f"Hi {invitee.first_name or invitee.username},\n\n"
                    f"{requestor.first_name or requestor.username} has invited you to join "
                    f"'{group.name}' on ChoreSync as a {role}.\n"
                    f"Use this code to join: {group.group_code}\n\n"
                    f"Or visit: {settings.FRONTEND_APP_URL}/join/{group.group_code}"
                ),
                context={"type": "group_invite", "group_id": str(group.id)},
            )
        else:
            # No account yet — send signup link with group code embedded
            AccountService()._send_and_log_email(
                to_address=email,
                subject=f"You're invited to join {group.name} on ChoreSync!",
                message=(
                    f"Hi,\n\n"
                    f"{requestor.first_name or requestor.username} has invited you to join "
                    f"'{group.name}' on ChoreSync.\n"
                    f"Sign up and use code {group.group_code} to join:\n"
                    f"{settings.FRONTEND_APP_URL}/join/{group.group_code}"
                ),
                context={"type": "group_invite", "group_id": str(group.id)},
            )

    def leave_group(self, *, user: User, group_id: str) -> bool:
        """Remove the requesting user from the group.

        Returns True if the group was deleted (user was the last member),
        False if the user simply left.

        Raises ValueError if:
          - The user is not a member.
          - The user is the only moderator but other members remain
            (they must promote someone first).
        """
        group = Group.objects.filter(id=group_id).first()
        if group is None:
            raise ValueError("Group not found.")

        membership = GroupMembership.objects.filter(user=user, group=group).first()
        if membership is None:
            raise ValueError("You are not a member of this group.")

        total_members = GroupMembership.objects.filter(group=group).count()

        if total_members == 1:
            # Last member — delete the whole group (cascades memberships, tasks, etc.)
            group.delete()
            return True

        # More than one member remains — check moderator constraint.
        if membership.role == 'moderator':
            other_moderators = GroupMembership.objects.filter(
                group=group, role='moderator'
            ).exclude(user=user).count()
            if other_moderators == 0:
                raise ValueError(
                    "You are the only moderator. Promote another member before leaving."
                )

        membership.delete()
        return False

    def compute_assignment_matrix(self, *, group_id: str) -> dict:
        """Build a fairness matrix used for automated task assignments.

        Inputs:
            group_id: Group whose workload distribution is being analyzed.
        Output:
            Dict keyed by user_id (str) → float score. Lower score = higher assignment priority.
        """
        group = Group.objects.filter(id=group_id).first()
        if group is None:
            raise ValueError("Group not found.")

        members = group.members.select_related('user').all()
        if not members.exists():
            raise ValueError(f"Group '{group.name}' has no members to assign tasks to")

        raw_matrix = {}

        for membership in members:
            user = membership.user
            stats = UserStats.objects.filter(user=user, household=group).first()

            if group.fairness_algorithm == 'count_based':
                score = stats.total_tasks_completed if stats else 0

            elif group.fairness_algorithm == 'time_based':
                from django.utils import timezone
                last = TaskOccurrence.objects.filter(
                    assigned_to=user, template__group=group
                ).order_by('-deadline').first()
                # Days since last assignment — more days = lower score = higher priority
                score = (timezone.now() - last.deadline).days if last else 0

            elif group.fairness_algorithm == 'difficulty_based':
                score = stats.total_points if stats else 0

            elif group.fairness_algorithm == 'weighted':
                tasks = stats.total_tasks_completed if stats else 0
                points = stats.total_points if stats else 0
                score = (tasks * 0.6) + (points * 0.4)

            else:
                score = stats.total_tasks_completed if stats else 0

            raw_matrix[str(user.id)] = score
        normalised_matrix = GroupOrchestrator._normalise(raw_matrix)
        return normalised_matrix

    def generate_invite_code(self,group : Group ,*, length: int = 6) -> None:
        """Produce a human-friendly invite code for group onboarding.

        Inputs:
            length: Desired code length (default 6).
        Output:
            None. Updates the Group with a new code and persists.
        """
        group.group_code = secrets.token_urlsafe(length).upper()
        group.save(update_fields=['group_code'])
