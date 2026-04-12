"""Task preference endpoints — lets members mark templates as prefer/neutral/avoid."""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from chore_sync.models import GroupMembership, TaskOccurrence, TaskPreference, TaskTemplate


class GroupPreferenceListAPIView(APIView):
    """GET /api/groups/<pk>/my-preferences/
    Returns only templates the caller has completed at least once, with their preference.
    """
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not GroupMembership.objects.filter(user=request.user, group_id=pk).exists():
            return Response({'detail': 'Not a member of this group.'}, status=403)

        # Only return templates the user has actually completed — preferences
        # on tasks you've never done are speculative and skew assignment.
        completed_template_ids = set(
            TaskOccurrence.objects.filter(
                assigned_to=request.user,
                template__group_id=pk,
                status='completed',
            ).values_list('template_id', flat=True).distinct()
        )

        templates = TaskTemplate.objects.filter(id__in=completed_template_ids, active=True)
        prefs = {
            p.task_template_id: p
            for p in TaskPreference.objects.filter(
                user=request.user, task_template__group_id=pk
            )
        }
        return Response([
            {
                'template_id': t.id,
                'template_name': t.name,
                'category': t.category,
                'preference': prefs[t.id].preference if t.id in prefs else 'neutral',
                'reason': prefs[t.id].reason if t.id in prefs else '',
            }
            for t in templates
        ])


class TaskPreferenceAPIView(APIView):
    """PUT /api/task-templates/<pk>/my-preference/
    Upsert the caller's preference for one template.
    Body: { preference: 'prefer'|'neutral'|'avoid', reason?: string }
    """
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    VALID = {'prefer', 'neutral', 'avoid'}

    def put(self, request, pk):
        template = TaskTemplate.objects.filter(id=pk, active=True).select_related('group').first()
        if template is None:
            return Response({'detail': 'Template not found.'}, status=404)

        if not GroupMembership.objects.filter(
            user=request.user, group=template.group
        ).exists():
            return Response({'detail': 'Not a member of this group.'}, status=403)

        # Only users who have completed this task can set a preference.
        has_completed = TaskOccurrence.objects.filter(
            assigned_to=request.user,
            template=template,
            status='completed',
        ).exists()
        if not has_completed:
            return Response(
                {'detail': 'You can only set a preference after completing this task.'},
                status=403,
            )

        preference = request.data.get('preference', 'neutral')
        if preference not in self.VALID:
            return Response(
                {'detail': f"preference must be one of {self.VALID}."},
                status=400,
            )
        reason = request.data.get('reason', '')

        pref, _ = TaskPreference.objects.update_or_create(
            user=request.user,
            task_template=template,
            defaults={'preference': preference, 'reason': reason},
        )
        return Response({
            'template_id': template.id,
            'template_name': template.name,
            'preference': pref.preference,
            'reason': pref.reason,
        })
