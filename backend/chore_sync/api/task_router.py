"""DRF views for task occurrence endpoints."""
from __future__ import annotations

from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from chore_sync.models import GroupMembership, TaskOccurrence, TaskSwap, TaskTemplate
from chore_sync.services.task_lifecycle_service import TaskLifecycleService

_svc = TaskLifecycleService()


def _serialize_occurrence(o: TaskOccurrence) -> dict:
    # Check if listed on marketplace (only when prefetched or via related manager)
    on_marketplace = False
    try:
        on_marketplace = hasattr(o, 'marketplace_listing') and o.marketplace_listing is not None
    except Exception:
        pass
    return {
        "id": o.id,
        "template_id": o.template_id,
        "template_name": o.template.name,
        "group_id": str(o.template.group_id),
        "group_name": o.template.group.name,
        "assigned_to_id": str(o.assigned_to_id) if o.assigned_to_id else None,
        "assigned_to_username": o.assigned_to.username if o.assigned_to_id and hasattr(o, 'assigned_to') and o.assigned_to else None,
        "deadline": o.deadline,
        "status": o.status,
        "completed_at": o.completed_at,
        "points_earned": o.points_earned,
        "snooze_count": o.snooze_count,
        "photo_proof_required": o.template.photo_proof_required,
        "photo_proof": o.photo_proof.url if o.photo_proof else None,
        "on_marketplace": on_marketplace,
    }


class UserTaskListAPIView(APIView):
    """GET /api/users/me/tasks/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        group_id = request.query_params.get('group_id')
        status_filter = request.query_params.get('status')
        result = _svc.list_user_tasks(
            user_id=str(request.user.id),
            group_id=group_id,
        )
        all_occurrences = []
        for occurrences in result.values():
            all_occurrences.extend(occurrences)
        if status_filter:
            all_occurrences = [o for o in all_occurrences if o.status == status_filter]
        return Response([_serialize_occurrence(o) for o in all_occurrences])


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
    task_name = None
    group_name = None
    if s.task_id and hasattr(s, 'task') and s.task:
        try:
            task_name = s.task.template.name
            group_name = s.task.template.group.name
        except Exception:
            pass
    from_username = None
    if s.from_user_id and hasattr(s, 'from_user') and s.from_user:
        from_username = s.from_user.username
    return {
        "id": s.id,
        "task_id": s.task_id,
        "task_name": task_name,
        "group_name": group_name,
        "from_user_id": str(s.from_user_id) if s.from_user_id else None,
        "from_username": from_username,
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


class PendingSwapsAPIView(APIView):
    """GET /api/users/me/pending-swaps/ — incoming swap requests directed at the current user."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils import timezone
        from chore_sync.models import GroupMembership
        user = request.user

        # Direct swaps sent to this user
        direct = list(
            TaskSwap.objects.select_related(
                'task__template__group', 'from_user'
            ).filter(
                to_user=user,
                status='pending',
                expires_at__gt=timezone.now(),
                swap_type='direct_swap',
            )
        )

        # Open requests in groups this user belongs to (excluding own requests)
        my_groups = GroupMembership.objects.filter(user=user).values_list('group_id', flat=True)
        open_req = list(
            TaskSwap.objects.select_related(
                'task__template__group', 'from_user'
            ).filter(
                status='pending',
                expires_at__gt=timezone.now(),
                swap_type='open_request',
                task__template__group_id__in=my_groups,
            ).exclude(from_user=user)
        )

        swaps = direct + open_req
        return Response([_serialize_swap(s) for s in swaps])


_ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/heic'}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


class TaskPhotoProofAPIView(APIView):
    """POST /api/tasks/{pk}/upload-proof/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        occurrence = TaskOccurrence.objects.select_related(
            'template__group', 'assigned_to'
        ).filter(id=pk).first()
        if occurrence is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        group = occurrence.template.group
        if not GroupMembership.objects.filter(user=request.user, group=group).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Only the assignee or a moderator may upload proof
        is_assigned = str(occurrence.assigned_to_id) == str(request.user.id)
        is_moderator = GroupMembership.objects.filter(
            user=request.user, group=group, role='moderator'
        ).exists()
        if not is_assigned and not is_moderator:
            return Response(
                {"detail": "Only the assigned user or a group moderator can upload proof."},
                status=status.HTTP_403_FORBIDDEN,
            )

        photo = request.FILES.get('photo')
        if photo is None:
            return Response({"detail": "photo file is required."}, status=status.HTTP_400_BAD_REQUEST)

        if photo.size > _MAX_UPLOAD_BYTES:
            return Response({"detail": "File too large. Maximum size is 5 MB."}, status=status.HTTP_400_BAD_REQUEST)

        if photo.content_type not in _ALLOWED_MIME_TYPES:
            return Response(
                {"detail": f"Unsupported file type '{photo.content_type}'. Upload a JPEG, PNG, GIF, WebP, or HEIC image."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        occurrence.photo_proof = photo
        occurrence.save(update_fields=['photo_proof'])

        return Response({"photo_url": occurrence.photo_proof.url}, status=status.HTTP_200_OK)
