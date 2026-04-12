"""DRF views for stats dashboard endpoints."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from chore_sync.services.insights_service import InsightsService

_svc = InsightsService()


class UserStatsAPIView(APIView):
    """GET /api/users/me/stats/ — stats across all households."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        stats = _svc.get_user_stats(user_id=str(request.user.id))
        return Response(stats)


class UserBadgesAPIView(APIView):
    """GET /api/users/me/badges/ — all earned badges."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        badges = _svc.get_user_badges(user_id=str(request.user.id))
        return Response(badges)


class GroupStatsAPIView(APIView):
    """GET /api/groups/{pk}/stats/ — household-level aggregates."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            stats = _svc.get_group_stats(
                group_id=str(pk),
                actor_id=str(request.user.id),
            )
        except PermissionError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(stats)
