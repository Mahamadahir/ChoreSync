"""DRF views for group management endpoints."""
from __future__ import annotations

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
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import Count
from chore_sync.models import GroupMembership, TaskOccurrence, UserStats
from chore_sync.services.group_service import GroupOrchestrator
from chore_sync.services.gamification_service import GamificationService

_gsvc = GamificationService()

User = get_user_model()
_svc = GroupOrchestrator()


class GroupListCreateAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = list(
            GroupMembership.objects.filter(user=request.user).select_related('group')
        )
        group_ids = [m.group_id for m in memberships]

        # Member counts per group (single query)
        member_counts = dict(
            GroupMembership.objects.filter(group_id__in=group_ids)
            .values('group_id')
            .annotate(cnt=Count('id'))
            .values_list('group_id', 'cnt')
        )

        # Open task counts per group — pending or in_progress (single query)
        open_task_counts = dict(
            TaskOccurrence.objects.filter(
                template__group_id__in=group_ids,
                status__in=['pending', 'in_progress'],
            )
            .values('template__group_id')
            .annotate(cnt=Count('id'))
            .values_list('template__group_id', 'cnt')
        )

        data = [
            {
                "id": str(m.group.id),
                "name": m.group.name,
                "group_code": m.group.group_code,
                "role": m.role,
                "my_role": m.role,
                "photo_proof_required": m.group.photo_proof_required,
                "member_count": member_counts.get(m.group_id, 0),
                "open_task_count": open_task_counts.get(m.group_id, 0),
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
                task_proposal_voting_required=serializer.validated_data.get('task_proposal_voting_required', False),
                group_type=serializer.validated_data.get('group_type', 'custom'),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"id": str(group.id), "name": group.name, "group_code": group.group_code},
            status=status.HTTP_201_CREATED,
        )


class GroupJoinByCodeAPIView(APIView):
    """POST /api/groups/join/ — join a group using its invite code."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '')
        try:
            group = _svc.join_by_code(user=request.user, code=code)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'id': str(group.id), 'name': group.name, 'group_code': group.group_code},
            status=status.HTTP_200_OK,
        )


class GroupDetailAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        membership = GroupMembership.objects.filter(
            user=request.user, group_id=pk
        ).select_related('group').first()
        if membership is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        g = membership.group
        member_count = GroupMembership.objects.filter(group=g).count()
        return Response({
            "id": str(g.id),
            "name": g.name,
            "group_code": g.group_code,
            "role": membership.role,
            "my_role": membership.role,
            "member_count": member_count,
            "reassignment_rule": g.reassignment_rule,
            "photo_proof_required": g.photo_proof_required,
            "task_proposal_voting_required": g.task_proposal_voting_required,
            "group_type": g.group_type,
        })


class GroupInviteAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = InviteMemberSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            _svc.invite_member(
                requestor=request.user,
                group_id=str(pk),
                email=serializer.validated_data['email'],
                role=serializer.validated_data['role'],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Invitation sent."}, status=status.HTTP_200_OK)


class GroupMembersAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not GroupMembership.objects.filter(user=request.user, group_id=pk).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        memberships = GroupMembership.objects.filter(
            group_id=pk
        ).select_related('user')
        user_ids = [m.user_id for m in memberships]
        stats_map = {
            s.user_id: s
            for s in UserStats.objects.filter(user_id__in=user_ids, household_id=pk)
        }
        data = []
        for m in memberships:
            stats = stats_map.get(m.user_id)
            data.append({
                "user_id": str(m.user.id),
                "email": m.user.email,
                "username": m.user.username,
                "first_name": m.user.first_name,
                "last_name": m.user.last_name,
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
        for field in ('name', 'photo_proof_required', 'task_proposal_voting_required'):
            if field in serializer.validated_data:
                setattr(group, field, serializer.validated_data[field])
                update_fields.append(field)
        if update_fields:
            group.save(update_fields=update_fields)

        return Response({
            "name": group.name,
            "photo_proof_required": group.photo_proof_required,
            "task_proposal_voting_required": group.task_proposal_voting_required,
            "group_type": group.group_type,
        })



class GroupLeaderboardAPIView(APIView):
    """GET /api/groups/{pk}/leaderboard/"""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            leaderboard = _gsvc.get_leaderboard(
                group_id=str(pk),
                actor_id=str(request.user.id),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(leaderboard)


class GroupLeaveAPIView(APIView):
    """POST /api/groups/{pk}/leave/"""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            group_deleted = _svc.leave_group(user=request.user, group_id=str(pk))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"group_deleted": group_deleted}, status=status.HTTP_200_OK)
