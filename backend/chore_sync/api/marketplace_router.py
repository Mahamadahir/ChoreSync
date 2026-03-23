"""DRF views for the Task Marketplace."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from chore_sync.models import MarketplaceListing
from chore_sync.services.marketplace_service import MarketplaceService

_svc = MarketplaceService()


def _serialize_listing(listing: MarketplaceListing) -> dict:
    occ = listing.task_occurrence
    return {
        "id": listing.id,
        "task_occurrence_id": occ.id,
        "task_name": occ.template.name,
        "group_id": str(listing.group_id),
        "listed_by_id": str(listing.listed_by_id),
        "listed_by_username": listing.listed_by.username,
        "bonus_points": listing.bonus_points,
        "deadline": occ.deadline,
        "expires_at": listing.expires_at,
        "created_at": listing.created_at,
    }


class TaskListMarketplaceAPIView(APIView):
    """POST /api/tasks/<pk>/list-marketplace/ — list a task on the marketplace."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        bonus_points = int(request.data.get('bonus_points', 0))
        try:
            listing = _svc.list_task(
                user=request.user,
                occurrence_id=str(pk),
                bonus_points=bonus_points,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_listing(listing), status=status.HTTP_201_CREATED)


class GroupMarketplaceListAPIView(APIView):
    """GET /api/groups/<pk>/marketplace/ — list active marketplace listings for a group."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            listings = _svc.list_active(
                group_id=str(pk),
                actor_id=str(request.user.id),
            )
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response([_serialize_listing(lst) for lst in listings])


class MarketplaceClaimAPIView(APIView):
    """POST /api/marketplace/<pk>/claim/ — claim a listing."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            occurrence = _svc.claim_task(
                user=request.user,
                listing_id=int(pk),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"detail": "Task claimed.", "task_occurrence_id": occurrence.id})
