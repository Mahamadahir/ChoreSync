"""Group management API endpoints."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("/")
async def create_group_endpoint() -> None:
    """Accept requests for creating a new group in ChoreSync.

    Inputs:
        JSON body (name, reassignment_rule, metadata).
    Output:
        201 response with the created group resource (id, invite code) or validation errors.
    TODO: Validate payload + authentication, delegate to GroupOrchestrator.create_group, translate domain errors, and return serialized group.
    """
    raise NotImplementedError("TODO: implement group creation endpoint")


@router.post("/invite")
async def invite_group_member_endpoint() -> None:
    """Send group invitations by email.

    Inputs:
        Body containing group_id and email of invitee.
    Output:
        JSON describing invite status, expiry, and next steps.
    TODO: Validate email + permissions, call GroupOrchestrator.invite_member, and return invite metadata (token, expiry).
    """
    raise NotImplementedError("TODO: implement group invitation endpoint")


@router.get("/{group_id}/assignment-matrix")
async def get_assignment_matrix_endpoint(group_id: str) -> None:
    """Expose the current fairness matrix for a group.

    Inputs:
        group_id: Path parameter identifying the group.
    Output:
        JSON containing assignment scores matrix for visualization.
    TODO: Authorize caller, call GroupOrchestrator.compute_assignment_matrix, format matrix for charting, and include metadata/timestamps.
    """
    raise NotImplementedError("TODO: implement assignment matrix endpoint")
