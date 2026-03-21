"""DRF views for task occurrence endpoints."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from chore_sync.models import GroupMembership, TaskOccurrence, TaskSwap, TaskTemplate
from chore_sync.services.task_lifecycle_service import TaskLifecycleService

_svc = TaskLifecycleService()


def _serialize_occurrence(o: TaskOccurrence) -> dict:
    return {
        "id": o.id,
        "template_id": o.template_id,
        "template_name": o.template.name,
        "group_id": str(o.template.group_id),
        "assigned_to_id": str(o.assigned_to_id) if o.assigned_to_id else None,
        "deadline": o.deadline,
        "status": o.status,
        "completed_at": o.completed_at,
        "points_earned": o.points_earned,
        "photo_proof": o.photo_proof.url if o.photo_proof else None,
    }


class UserTaskListAPIView(APIView):
    """GET /api/users/me/tasks/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_id = request.query_params.get('group_id')
        result = _svc.list_user_tasks(
            user_id=str(request.user.id),
            group_id=group_id,
        )
        return Response({
            bucket: [_serialize_occurrence(o) for o in occurrences]
            for bucket, occurrences in result.items()
        })


class GroupTaskListAPIView(APIView):
    """GET /api/groups/{pk}/tasks/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            occurrences = _svc.list_group_tasks(
                group_id=str(pk),
                actor_id=str(request.user.id),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response([_serialize_occurrence(o) for o in occurrences])


class GenerateOccurrencesAPIView(APIView):
    """POST /api/task-templates/{pk}/generate-occurrences/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        template = TaskTemplate.objects.select_related('group').filter(id=pk, active=True).first()
        if template is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not GroupMembership.objects.filter(user=request.user, group=template.group).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        horizon_days = int(request.data.get('horizon_days', 7))
        try:
            created = _svc.generate_recurring_instances(
                task_template_id=str(pk),
                horizon_days=horizon_days,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"created": len(created), "occurrences": [_serialize_occurrence(o) for o in created]},
            status=status.HTTP_201_CREATED,
        )


class TaskOccurrenceDetailAPIView(APIView):
    """PATCH /api/tasks/{pk}/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_occurrence_for_user(self, pk, user):
        occ = TaskOccurrence.objects.select_related('template__group').filter(id=pk).first()
        if occ is None:
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not GroupMembership.objects.filter(user=user, group=occ.template.group).exists():
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return occ, None

    def patch(self, request, pk):
        occ, err = self._get_occurrence_for_user(pk, request.user)
        if err:
            return err
        allowed = {'status', 'assigned_to_id'}
        for field, value in request.data.items():
            if field in allowed:
                setattr(occ, field, value)
        occ.save()
        return Response(_serialize_occurrence(occ))


class TaskCompleteAPIView(APIView):
    """POST /api/tasks/{pk}/complete/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        completed = request.data.get('completed', True)
        try:
            occurrence = _svc.toggle_occurrence_completed(
                occurrence_id=str(pk),
                completed=bool(completed),
                actor_id=str(request.user.id),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_occurrence(occurrence))


def _serialize_swap(s: TaskSwap) -> dict:
    return {
        "id": s.id,
        "task_id": s.task_id,
        "from_user_id": str(s.from_user_id) if s.from_user_id else None,
        "to_user_id": str(s.to_user_id) if s.to_user_id else None,
        "swap_type": s.swap_type,
        "status": s.status,
        "reason": s.reason,
        "expires_at": s.expires_at,
        "decided_at": s.decided_at,
    }


class TaskSnoozeAPIView(APIView):
    """POST /api/tasks/{pk}/snooze/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        snooze_until = request.data.get('snooze_until')
        if not snooze_until:
            return Response({"detail": "snooze_until is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from django.utils.dateparse import parse_datetime
            snooze_until_dt = parse_datetime(snooze_until)
            if snooze_until_dt is None:
                raise ValueError("Invalid datetime format for snooze_until.")
            occurrence = _svc.snooze_task(
                occurrence_id=str(pk),
                snooze_until=snooze_until_dt,
                actor_id=str(request.user.id),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_occurrence(occurrence))


class TaskSwapCreateAPIView(APIView):
    """POST /api/tasks/{pk}/swap/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            swap = _svc.create_swap_request(
                task_id=str(pk),
                from_user_id=str(request.user.id),
                reason=request.data.get('reason', ''),
                to_user_id=request.data.get('to_user_id'),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_swap(swap), status=status.HTTP_201_CREATED)


class TaskSwapRespondAPIView(APIView):
    """POST /api/task-swaps/{pk}/respond/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        accept = request.data.get('accept')
        if accept is None:
            return Response({"detail": "accept (true/false) is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            swap = _svc.respond_to_swap_request(
                swap_id=str(pk),
                accept=bool(accept),
                actor_id=str(request.user.id),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_swap(swap))


class TaskEmergencyReassignAPIView(APIView):
    """POST /api/tasks/{pk}/emergency-reassign/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            occurrence = _svc.emergency_reassign(
                occurrence_id=str(pk),
                actor_id=str(request.user.id),
                reason=request.data.get('reason', ''),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_occurrence(occurrence))


class TaskAcceptEmergencyAPIView(APIView):
    """POST /api/tasks/{pk}/accept-emergency/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            occurrence = _svc.accept_emergency(
                occurrence_id=str(pk),
                actor_id=str(request.user.id),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_occurrence(occurrence))
