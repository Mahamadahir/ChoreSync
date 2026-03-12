"""DRF views for group management endpoints."""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.serializers import (
    CreateGroupSerializer,
    GroupSettingsSerializer,
    InviteMemberSerializer,
)
from chore_sync.api.views import CsrfExemptSessionAuthentication
from chore_sync.models import Group, GroupMembership, UserStats
from chore_sync.services.auth_service import AccountService
from chore_sync.services.group_service import GroupOrchestrator

User = get_user_model()
_svc = GroupOrchestrator()


class GroupListCreateAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = GroupMembership.objects.filter(
            user=request.user
        ).select_related('group')
        data = [
            {
                "id": str(m.group.id),
                "name": m.group.name,
                "group_code": m.group.group_code,
                "role": m.role,
                "fairness_algorithm": m.group.fairness_algorithm,
                "photo_proof_required": m.group.photo_proof_required,
            }
            for m in memberships
        ]
        return Response(data)

    def post(self, request):
        serializer = CreateGroupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            group = _svc.create_group(
                owner=request.user,
                name=serializer.validated_data['name'],
                reassignment_rule=serializer.validated_data.get('reassignment_rule'),
                fairness_algorithm=serializer.validated_data.get('fairness_algorithm'),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"id": str(group.id), "name": group.name, "group_code": group.group_code},
            status=status.HTTP_201_CREATED,
        )


class GroupDetailAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        membership = GroupMembership.objects.filter(
            user=request.user, group_id=pk
        ).select_related('group').first()
        if membership is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        g = membership.group
        return Response({
            "id": str(g.id),
            "name": g.name,
            "group_code": g.group_code,
            "role": membership.role,
            "fairness_algorithm": g.fairness_algorithm,
            "reassignment_rule": g.reassignment_rule,
            "photo_proof_required": g.photo_proof_required,
            "task_proposal_voting_required": g.task_proposal_voting_required,
        })


class GroupInviteAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = InviteMemberSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        role = serializer.validated_data['role']
        invitee = User.objects.filter(email=email).first()

        if invitee:
            try:
                _svc.invite_member(
                    requestor=request.user,
                    invitee=invitee,
                    group_id=str(pk),
                    email=email,
                    role=role,
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # User doesn't have an account yet — send email with group code only
            group = Group.objects.filter(id=pk).first()
            if group is None:
                return Response({"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND)
            requestor_membership = group.members.filter(user=request.user).first()
            if requestor_membership is None or requestor_membership.role != 'moderator':
                return Response(
                    {"detail": "Only moderators can invite members."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            AccountService()._send_and_log_email(
                to_address=email,
                subject=f"You're invited to join {group.name} on ChoreSync!",
                message=(
                    f"Hi,\n\nYou've been invited to join '{group.name}' on ChoreSync.\n"
                    f"Sign up and use code {group.group_code} to join:\n"
                    f"{settings.FRONTEND_APP_URL}/join/{group.group_code}"
                ),
                context={"type": "group_invite", "group_id": str(group.id)},
            )

        return Response({"detail": "Invitation sent."}, status=status.HTTP_200_OK)


class GroupMembersAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not GroupMembership.objects.filter(user=request.user, group_id=pk).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        memberships = GroupMembership.objects.filter(
            group_id=pk
        ).select_related('user')
        data = []
        for m in memberships:
            stats = UserStats.objects.filter(user=m.user, household_id=pk).first()
            data.append({
                "user_id": str(m.user.id),
                "email": m.user.email,
                "username": m.user.username,
                "role": m.role,
                "joined_at": m.joined_at,
                "stats": {
                    "total_tasks_completed": stats.total_tasks_completed,
                    "total_points": stats.total_points,
                    "tasks_completed_this_week": stats.tasks_completed_this_week,
                    "on_time_completion_rate": stats.on_time_completion_rate,
                    "current_streak_days": stats.current_streak_days,
                } if stats else None,
            })
        return Response(data)


class GroupAssignmentMatrixAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not GroupMembership.objects.filter(user=request.user, group_id=pk).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            matrix = _svc.compute_assignment_matrix(group_id=str(pk))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(matrix)


class GroupSettingsAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        membership = GroupMembership.objects.filter(
            user=request.user, group_id=pk
        ).select_related('group').first()
        if membership is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if membership.role != 'moderator':
            return Response(
                {"detail": "Only moderators can update group settings."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = GroupSettingsSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        group = membership.group
        update_fields = []
        for field in ('fairness_algorithm', 'photo_proof_required', 'task_proposal_voting_required'):
            if field in serializer.validated_data:
                setattr(group, field, serializer.validated_data[field])
                update_fields.append(field)
        if update_fields:
            group.save(update_fields=update_fields)

        return Response({
            "fairness_algorithm": group.fairness_algorithm,
            "photo_proof_required": group.photo_proof_required,
            "task_proposal_voting_required": group.task_proposal_voting_required,
        })
