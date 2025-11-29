"""Authentication API endpoints (stubs)."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup_endpoint() -> None:
    """Register a new user account (username/email/password).

    Inputs:
        JSON body containing username, email, password (and optional profile fields).
    Output:
        201 on success with a user summary DTO and verification status,
        or 4xx with validation errors.
    TODO: Validate payload, call AccountService.register_user, and map domain errors to HTTP responses.
    """
    raise NotImplementedError("TODO: implement signup endpoint")


@router.post("/login")
async def login_endpoint() -> None:
    """Authenticate an existing user.

    Inputs:
        JSON body with identifier (email/username) and password.
    Output:
        200 with session/token info, or 401/403 for invalid credentials/inactive accounts.
    TODO: Validate payload, delegate to AccountService.authenticate (to be implemented), and issue session/token.
    """
    raise NotImplementedError("TODO: implement login endpoint")
