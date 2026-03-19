"""DRF views for task template endpoints."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from chore_sync.models import GroupMembership, TaskTemplate
from chore_sync.services.task_template_service import TaskTemplateService

_svc = TaskTemplateService()

TEMPLATE_FIELDS = ('name', 'details', 'recurring_choice', 'difficulty',
                   'estimated_mins', 'category', 'next_due', 'days_of_week', 'recur_value', 'importance')


def _serialize(t: TaskTemplate) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "details": t.details,
        "recurring_choice": t.recurring_choice,
        "days_of_week": t.days_of_week,
        "difficulty": t.difficulty,
        "estimated_mins": t.estimated_mins,
        "category": t.category,
        "recur_value": t.recur_value,
        "next_due": t.next_due,
        "active": t.active,
        "importance": t.importance,
        "group_id": str(t.group_id),
        "creator_id": str(t.creator_id) if t.creator_id else None,
    }


class GroupTaskTemplateListCreateAPIView(APIView):
    """GET/POST /api/groups/{pk}/task-templates/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not GroupMembership.objects.filter(user=request.user, group_id=pk).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        templates = _svc.list_templates(group_id=str(pk))
        return Response([_serialize(t) for t in templates])

    def post(self, request, pk):
        if not GroupMembership.objects.filter(user=request.user, group_id=pk).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        payload = {k: v for k, v in request.data.items() if k in TEMPLATE_FIELDS}
        try:
            template = _svc.create_template(
                creator=request.user,
                group_id=str(pk),
                payload=payload,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_serialize(template), status=status.HTTP_201_CREATED)


class TaskTemplateDetailAPIView(APIView):
    """GET/PATCH/DELETE /api/task-templates/{pk}/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_template_for_user(self, pk, user):
        template = TaskTemplate.objects.select_related('group').filter(id=pk, active=True).first()
        if template is None:
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not GroupMembership.objects.filter(user=user, group=template.group).exists():
            return None, Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return template, None

    def get(self, request, pk):
        template, err = self._get_template_for_user(pk, request.user)
        if err:
            return err
        return Response(_serialize(template))

    def patch(self, request, pk):
        updates = {k: v for k, v in request.data.items() if k in TEMPLATE_FIELDS}
        try:
            template = _svc.update_template(
                template_id=str(pk),
                actor_id=str(request.user.id),
                updates=updates,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_serialize(template))

    def delete(self, request, pk):
        try:
            _svc.delete_template(
                template_id=str(pk),
                actor_id=str(request.user.id),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)
