"""Group management services for ChoreSync."""
from __future__ import annotations
from dataclasses import dataclass
from django.db import transaction
from django.conf import settings
import secrets
from chore_sync.models import Group, User, GroupMembership, Notification, UserStats, TaskOccurrence
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


    def create_group(
        self,
        *,
        owner: User,
        name: str,
        reassignment_rule: str | None = None,
        task_proposal_voting_required: bool = False,
        group_type: str = 'custom',
    ) -> Group:
        """Provision a new group and default configuration.

        Inputs:
            owner: User creating the group (initial admin).
            name: Human-friendly group name.
            reassignment_rule: Initial fairness/rotation setting identifier.
            task_proposal_voting_required: Whether new task templates require a group vote.
        Output:
            Group DTO (id, slug, invite code) ready for UI consumption.
        """
        valid_rules = [c[0] for c in Group._meta.get_field('reassignment_rule').choices]
        if name is None or len(name) == 0:
            raise ValueError("Group name cannot be empty.")
        if len(name) > 100:
            raise ValueError("Group name cannot exceed 100 characters.")

        if reassignment_rule is not None and reassignment_rule not in valid_rules:
            raise ValueError(f"Invalid reassignment rule: {reassignment_rule}")

        with transaction.atomic():
            group = Group.objects.create(
                name=name,
                owner=owner,
                reassignment_rule=reassignment_rule,
                group_code=secrets.token_urlsafe(6).upper(),
                task_proposal_voting_required=task_proposal_voting_required,
                group_type=group_type,
            )
            GroupMembership.objects.create(user=owner, group=group, role='moderator')
        return group

    def join_by_code(self, *, user, code: str):
        """Join a group using its invite code.

        Inputs:
            user: The requesting user.
            code: The group_code string (case-insensitive).
        Output:
            The Group instance that was joined.
        """
        from chore_sync.models import Group
        normalised = code.strip().upper()
        if not normalised:
            raise ValueError("Group code cannot be empty.")
        group = Group.objects.filter(group_code=normalised).first()
        if group is None:
            raise ValueError("No group found with that code. Double-check and try again.")
        if GroupMembership.objects.filter(user=user, group=group).exists():
            raise ValueError("You are already a member of this group.")
        # Flatshares: everyone who joins via code is a moderator (peer group).
        role = 'moderator' if group.group_type == 'flatshare' else 'member'
        GroupMembership.objects.create(user=user, group=group, role=role)
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

        # Flatshares are peer groups — all members are moderators regardless of what was passed.
        if group.group_type == 'flatshare':
            role = 'moderator'

        invitee = User.objects.filter(email=email).first()

        if invitee is not None:
            if group.members.filter(user=invitee).exists():
                raise ValueError("User is already a member of the group.")
            with transaction.atomic():
                GroupMembership.objects.create(user=invitee, group=group, role=role)
            # Use the full notification pipeline so the invite gets realtime WS/SSE
            # delivery and respects the invitee's notification preferences.
            from chore_sync.services.notification_service import NotificationService
            NotificationService().emit_notification(
                recipient_id=str(invitee.id),
                notification_type='group_invite',
                title="Group Invitation",
                content=f"You have been invited to join the group '{group.name}' as a {role}.",
                group_id=str(group.id),
                action_url=f"/groups/{group.id}",
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
        """Build a unified fairness matrix used for automated task assignments.

        Blends three independently-normalised workload signals:
          - Task count  (40%) — who has completed the fewest tasks
          - Time burden (35%) — total estimated minutes of assigned tasks
          - Point load  (25%) — total points earned (reflects difficulty)

        Each signal is normalised 0→1 across the current member pool before
        blending, so members with very different task profiles are compared
        fairly. Lower blended score = higher assignment priority.

        Inputs:
            group_id: Group whose workload distribution is being analyzed.
        Output:
            Dict keyed by user_id (str) → float score (0–1, lower = next in line).
        """
        from django.db.models import Case, ExpressionWrapper, FloatField, Sum as _Sum, Value, When

        group = Group.objects.filter(id=group_id).first()
        if group is None:
            raise ValueError("Group not found.")

        members = list(group.members.select_related('user').all())
        if not members:
            raise ValueError(f"Group '{group.name}' has no members to assign tasks to")

        # Gather raw signals for every member in a single pass
        tasks_raw: dict[str, float] = {}
        time_raw: dict[str, float] = {}
        points_raw: dict[str, float] = {}

        # Difficulty-weighted time burden — harder tasks contribute more to a
        # member's time load, making them less likely to be assigned the next task.
        # Weights: easy(1)×0.8, (2)×0.9, medium(3)×1.0, hard(4)×1.25, expert(5)×1.6
        _difficulty_weight = ExpressionWrapper(
            Case(
                When(template__difficulty=1, then=Value(0.8)),
                When(template__difficulty=2, then=Value(0.9)),
                When(template__difficulty=3, then=Value(1.0)),
                When(template__difficulty=4, then=Value(1.25)),
                When(template__difficulty=5, then=Value(1.6)),
                default=Value(1.0),
                output_field=FloatField(),
            ),
            output_field=FloatField(),
        )
        _weighted_mins = ExpressionWrapper(
            Case(
                When(template__estimated_mins__isnull=False, then=ExpressionWrapper(
                    Case(
                        When(template__difficulty=1, then=Value(0.8)),
                        When(template__difficulty=2, then=Value(0.9)),
                        When(template__difficulty=3, then=Value(1.0)),
                        When(template__difficulty=4, then=Value(1.25)),
                        When(template__difficulty=5, then=Value(1.6)),
                        default=Value(1.0),
                        output_field=FloatField(),
                    ) * Case(
                        When(template__estimated_mins__isnull=False, then='template__estimated_mins'),
                        default=Value(30.0),
                        output_field=FloatField(),
                    ),
                    output_field=FloatField(),
                )),
                default=Value(30.0),
                output_field=FloatField(),
            ),
            output_field=FloatField(),
        )

        # Bulk difficulty-weighted time query to avoid N+1
        time_by_user = dict(
            TaskOccurrence.objects.filter(
                template__group=group,
                status__in=['completed', 'pending', 'snoozed'],
            )
            .values('assigned_to_id')
            .annotate(total=_Sum(_weighted_mins))
            .values_list('assigned_to_id', 'total')
        )

        for membership in members:
            user = membership.user
            uid = str(user.id)
            stats = UserStats.objects.filter(user=user, household=group).first()
            tasks_raw[uid] = float(stats.total_tasks_completed if stats else 0)
            time_raw[uid] = float(time_by_user.get(user.id) or 0)
            points_raw[uid] = float(stats.total_points if stats else 0)

        # Normalise each signal independently (0–1 within the group)
        tasks_norm = GroupOrchestrator._normalise(tasks_raw)
        time_norm = GroupOrchestrator._normalise(time_raw)
        points_norm = GroupOrchestrator._normalise(points_raw)

        # Blend and return — already in 0–1 range, no second normalise needed
        return {
            uid: tasks_norm[uid] * 0.40 + time_norm[uid] * 0.35 + points_norm[uid] * 0.25
            for uid in tasks_norm
        }

    def generate_invite_code(self,group : Group ,*, length: int = 6) -> None:
        """Produce a human-friendly invite code for group onboarding.

        Inputs:
            length: Desired code length (default 6).
        Output:
            None. Updates the Group with a new code and persists.
        """
        group.group_code = secrets.token_urlsafe(length).upper()
        group.save(update_fields=['group_code'])
