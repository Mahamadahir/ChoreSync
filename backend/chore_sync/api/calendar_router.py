"""Calendar synchronization API endpoints."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/calendars", tags=["calendars"])


@router.post("/google/sync")
async def sync_google_calendar_endpoint() -> None:
    """Kick off an incremental sync against Google Calendar for the authenticated user.

    Inputs:
        Authenticated user context plus optional query params (since token).
    Output:
        Accepted response containing job/correlation id for tracking.
    TODO: Resolve user + credentials, parse optional since timestamps, invoke CalendarSyncService.sync_google_calendar asynchronously, and return job metadata.
    """
    raise NotImplementedError("TODO: implement Google Calendar sync endpoint")


@router.post("/apple/sync")
async def sync_apple_calendar_endpoint() -> None:
    """Kick off an incremental sync against Apple Calendar for the authenticated user.

    Inputs:
        Authenticated user context; may include since timestamp.
    Output:
        Response acknowledging sync kickoff with tracking information.
    TODO: Resolve CalDAV credentials, call CalendarSyncService.sync_apple_calendar, handle 2FA prompts if required, and return correlation data.
    """
    raise NotImplementedError("TODO: implement Apple Calendar sync endpoint")


@router.post("/outlook/sync")
async def sync_outlook_calendar_endpoint() -> None:
    """Kick off an incremental sync against Outlook via Microsoft Graph for the user.

    Inputs:
        Authenticated user context plus optional deltaLink parameter.
    Output:
        Response with sync job identifier and next steps.
    TODO: Acquire Microsoft Graph tokens, call CalendarSyncService.sync_outlook_calendar, register deltaLink checkpoints, and return tracking metadata.
    """
    raise NotImplementedError("TODO: implement Outlook Calendar sync endpoint")
