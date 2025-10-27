"""Calendar synchronization API endpoints."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/calendars", tags=["calendars"])


@router.post("/google/sync")
async def sync_google_calendar_endpoint() -> None:
    """Kick off an incremental sync against Google Calendar for the authenticated user.

    TODO: Resolve the current user, call CalendarSyncService.sync_google_calendar, and
    return correlation identifiers for client-side polling.
    """
    raise NotImplementedError("TODO: implement Google Calendar sync endpoint")


@router.post("/apple/sync")
async def sync_apple_calendar_endpoint() -> None:
    """Kick off an incremental sync against Apple Calendar for the authenticated user.

    TODO: Resolve CalDAV credentials, call CalendarSyncService.sync_apple_calendar, and
    handle any required two-factor prompts with async workflows.
    """
    raise NotImplementedError("TODO: implement Apple Calendar sync endpoint")


@router.post("/outlook/sync")
async def sync_outlook_calendar_endpoint() -> None:
    """Kick off an incremental sync against Outlook via Microsoft Graph for the user.

    TODO: Acquire Microsoft Graph tokens, call CalendarSyncService.sync_outlook_calendar,
    and register delta link checkpoints for subsequent sync calls.
    """
    raise NotImplementedError("TODO: implement Outlook Calendar sync endpoint")
