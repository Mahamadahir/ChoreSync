"""DRF views for task template endpoints."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from chore_sync.models import Group, GroupMembership, TaskOccurrence, TaskTemplate
from chore_sync.services.task_lifecycle_service import TaskLifecycleService
from chore_sync.services.task_template_service import TaskTemplateService

_lifecycle_svc = TaskLifecycleService()

_svc = TaskTemplateService()

TEMPLATE_FIELDS = ('name', 'details', 'recurring_choice', 'difficulty',
                   'estimated_mins', 'category', 'next_due', 'days_of_week',
                   'recur_value', 'importance', 'photo_proof_required')


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
        "photo_proof_required": t.photo_proof_required,
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
        import datetime
        from django.utils import timezone as tz

        if not GroupMembership.objects.filter(user=request.user, group_id=pk).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)

        # Accept a full datetime string (ISO 8601) as next_due directly.
        # Fall back to legacy base_deadline_time (HH:MM) for backwards compatibility.
        if 'next_due' not in data or not data['next_due']:
            base_time_str = data.pop('base_deadline_time', None)
            if base_time_str:
                try:
                    time_part = datetime.datetime.strptime(base_time_str, '%H:%M').time()
                    today = tz.now().date()
                    data['next_due'] = datetime.datetime.combine(
                        today, time_part, tzinfo=datetime.timezone.utc
                    ).isoformat()
                except ValueError:
                    return Response(
                        {"detail": "Invalid base_deadline_time format. Use HH:MM."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"detail": "next_due or base_deadline_time is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            data.pop('base_deadline_time', None)

        payload = {k: v for k, v in data.items() if k in TEMPLATE_FIELDS}
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

        # Auto-generate occurrences based on template type + group rule.
        group = Group.objects.filter(id=pk).first()
        occurrences = []
        try:
            if template.recurring_choice == 'none':
                # One-time task: immediately materialise the single occurrence and assign it.
                occurrence, created = TaskOccurrence.objects.get_or_create(
                    template=template,
                    deadline=template.next_due,
                )
                if created:
                    _lifecycle_svc.assign_occurrence(occurrence)
                occurrences = [occurrence]
            elif group and group.reassignment_rule == 'on_create':
                # Recurring + group auto-assigns on every new template: generate first batch.
                occurrences = _lifecycle_svc.generate_recurring_instances(
                    task_template_id=str(template.id),
                    horizon_days=30,
                )
        except Exception:
            pass  # Occurrence generation failure is non-fatal; template is already saved.

        response_data = _serialize(template)
        response_data['occurrences_created'] = len(occurrences)
        return Response(response_data, status=status.HTTP_201_CREATED)


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
