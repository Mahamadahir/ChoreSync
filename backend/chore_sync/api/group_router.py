"""Group management API endpoints."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("/")
async def create_group_endpoint() -> None:
    """Accept requests for creating a new group in ChoreSync.

    TODO: Parse the payload, hand off to GroupOrchestrator.create_group, and return the
    newly created resource identifier once committed.
    """
    raise NotImplementedError("TODO: implement group creation endpoint")


@router.post("/invite")
async def invite_group_member_endpoint() -> None:
    """Send group invitations by email.

    TODO: Validate the email address, call GroupOrchestrator.invite_member, and surface
    invitation expiry metadata in the response payload.
    """
    raise NotImplementedError("TODO: implement group invitation endpoint")


@router.get("/{group_id}/assignment-matrix")
async def get_assignment_matrix_endpoint(group_id: str) -> None:
    """Expose the current fairness matrix for a group.

    TODO: Authorize the caller, call GroupOrchestrator.compute_assignment_matrix, and
    return structured data for client-side visualization.
    """
    raise NotImplementedError("TODO: implement assignment matrix endpoint")
