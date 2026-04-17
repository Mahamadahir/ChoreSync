"""DRF views for task occurrence endpoints."""
from __future__ import annotations

import logging

from rest_framework import status

logger = logging.getLogger(__name__)
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from chore_sync.models import GroupMembership, TaskAssignmentHistory, TaskOccurrence, TaskSwap, TaskTemplate
from chore_sync.services.task_lifecycle_service import TaskLifecycleService

_svc = TaskLifecycleService()


def _serialize_occurrence(o: TaskOccurrence) -> dict:
    # Check if listed on marketplace (only when prefetched or via related manager)
    on_marketplace = False
    marketplace_listing_id = None
    try:
        listing = o.marketplace_listing if hasattr(o, 'marketplace_listing') else None
        if listing is not None:
            on_marketplace = True
            marketplace_listing_id = listing.id
    except Exception:
        logger.exception("_serialize_occurrence: marketplace relation broken for occurrence_id=%s", o.id)
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
        "marketplace_listing_id": marketplace_listing_id,
        "reassignment_reason": o.reassignment_reason,
        "original_assignee_id": str(o.original_assignee_id) if o.original_assignee_id else None,
        # Template detail fields (used by mobile task detail screen)
        "template_details": o.template.details if hasattr(o, 'template') and o.template else None,
        "estimated_mins": o.template.estimated_mins if hasattr(o, 'template') and o.template else None,
        "difficulty": o.template.difficulty if hasattr(o, 'template') and o.template else None,
        "assignee_first_name": o.assigned_to.first_name if o.assigned_to_id and hasattr(o, 'assigned_to') and o.assigned_to else None,
        "assignee_last_name": o.assigned_to.last_name if o.assigned_to_id and hasattr(o, 'assigned_to') and o.assigned_to else None,
    }


class UserTaskListAPIView(APIView):
    """GET /api/users/me/tasks/"""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    """GET/PATCH /api/tasks/{pk}/. Note: GET is used by both clients to load task detail."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_occurrence_for_user(self, pk, user):
        occ = TaskOccurrence.objects.select_related('template__group', 'assigned_to').filter(id=pk).first()
        if occ is None:
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not GroupMembership.objects.filter(user=user, group=occ.template.group).exists():
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return occ, None

    def get(self, request, pk):
        occ, err = self._get_occurrence_for_user(pk, request.user)
        if err:
            return err
        return Response(_serialize_occurrence(occ))

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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
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


class TaskAcceptSuggestionAPIView(APIView):
    """POST /api/tasks/{pk}/accept-suggestion/ — accept a pre-assignment suggestion."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            occurrence = _svc.accept_suggestion(
                occurrence_id=pk,
                actor_id=str(request.user.id),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_occurrence(occurrence))


class TaskDeclineSuggestionAPIView(APIView):
    """POST /api/tasks/{pk}/decline-suggestion/ — decline a pre-assignment suggestion."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            occurrence = _svc.decline_suggestion(
                occurrence_id=pk,
                actor_id=str(request.user.id),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_occurrence(occurrence))


class TaskOccurrenceAssignmentBreakdownAPIView(APIView):
    """GET /api/tasks/{pk}/assignment-breakdown/

    Returns per-candidate scores from the pipeline run that produced the
    current assignment. Asymmetric disclosure: everyone sees final_score bars;
    only the requesting user sees their own component breakdown.

    Response when breakdown_available=true:
        {
          "occurrence_id": 42,
          "template_name": "Vacuum Living Room",
          "assigned_at": "2026-04-08T10:30:00Z",
          "winner_id": "uuid",
          "breakdown_available": true,
          "candidates": [
            { "user_id": "...", "username": "alice", "is_winner": true,
              "final_score": 28, "is_me": false },
            { "user_id": "...", "username": "bob", "is_winner": false,
              "final_score": 55, "is_me": true,
              "components": {
                "stage1_score": 42, "pref_multiplier": 0.8,
                "affinity_multiplier": 1.0, "calendar_penalty": 5
              }
            }
          ]
        }

    Scores are returned as integers (original ×100) for display purposes.
    """
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        # Verify membership
        occ = (
            TaskOccurrence.objects
            .select_related('template__group')
            .filter(id=pk)
            .first()
        )
        if occ is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not GroupMembership.objects.filter(
            user=request.user, group=occ.template.group
        ).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Fetch the pipeline-run history row (not swaps / emergency / marketplace)
        history = (
            TaskAssignmentHistory.objects
            .filter(
                task_occurrence=occ,
                was_swapped=False,
                was_emergency=False,
                was_marketplace=False,
            )
            .order_by('assigned_at')
            .first()
        )

        # Emergency cover: task was accepted by a volunteer, not assigned by the pipeline.
        # This is true when reassignment_reason='emergency' AND there is no subsequent
        # pipeline history row (auto-reassignment via pipeline creates one with was_emergency=False).
        if occ.reassignment_reason == 'emergency' and (history is None or history.score_breakdown is None):
            original_username = None
            if occ.original_assignee_id:
                from django.contrib.auth import get_user_model
                orig = get_user_model().objects.filter(id=occ.original_assignee_id).values('username').first()
                original_username = orig['username'] if orig else None
            covered_by = occ.assigned_to.username if occ.assigned_to else None
            return Response({
                "occurrence_id": occ.id,
                "template_name": occ.template.name,
                "breakdown_available": False,
                "assigned_via": "emergency_cover",
                "covered_by": covered_by,
                "original_assignee": original_username,
                "candidates": [],
            })

        if history is None or history.score_breakdown is None:
            return Response({
                "occurrence_id": occ.id,
                "template_name": occ.template.name,
                "breakdown_available": False,
                "candidates": [],
            })

        bd = history.score_breakdown
        my_id = str(request.user.id)

        candidates = []
        for c in bd.get('candidates', []):
            uid = c['user_id']
            entry: dict = {
                "user_id": uid,
                "username": c['username'],
                "is_winner": uid == bd['winner_id'],
                "final_score": round(c['final_score'] * 100),
                "is_me": uid == my_id,
            }
            if uid == my_id:
                entry["components"] = {
                    "stage1_score": round(c['stage1_score'] * 100),
                    "tasks_score": round(c.get('tasks_score', 0) * 100),
                    "time_score": round(c.get('time_score', 0) * 100),
                    "points_score": round(c.get('points_score', 0) * 100),
                    "pref_multiplier": c['pref_multiplier'],
                    "affinity_multiplier": c['affinity_multiplier'],
                    "calendar_penalty": round(c['calendar_penalty'] * 100),
                }
            candidates.append(entry)

        # Sort: winner first, then by final_score ascending
        candidates.sort(key=lambda x: (not x['is_winner'], x['final_score']))

        return Response({
            "occurrence_id": occ.id,
            "template_name": occ.template.name,
            "assigned_at": history.assigned_at.isoformat(),
            "winner_id": bd['winner_id'],
            "breakdown_available": True,
            "candidates": candidates,
        })
