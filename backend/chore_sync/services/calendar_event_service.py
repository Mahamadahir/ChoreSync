"""In-app calendar event services for ChoreSync."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CalendarEventService:
    """Manages creation and maintenance of in-app calendar events."""

    def create_in_app_event(self, *, calendar_id: str, title: str, start: datetime, duration_hours: float, description: str | None) -> None:
        """Create an event within the in-app calendar system."""
        # TODO: Validate conflicts, persist the event, and link to originating tasks when applicable.
        raise NotImplementedError("TODO: implement in-app event creation")

    def list_in_app_events(self, *, user_id: str, calendar_id: str | None = None) -> None:
        """List events for a user or specific in-app calendar."""
        # TODO: Query events, apply permission filters, and order results for client consumption.
        raise NotImplementedError("TODO: implement in-app event listing")

    def update_in_app_event(self, *, event_id: str, updates: dict) -> None:
        """Apply partial updates to an in-app event."""
        # TODO: Validate update fields, persist changes, and reschedule sync operations.
        raise NotImplementedError("TODO: implement in-app event update")

    def delete_in_app_event(self, *, event_id: str) -> None:
        """Remove an in-app event."""
        # TODO: Handle cascading deletes, detach external sync records, and notify attendees.
        raise NotImplementedError("TODO: implement in-app event deletion")

    def list_group_occurrences(self, *, group_id: str) -> None:
        """Retrieve upcoming occurrences for tasks in a group."""
        # TODO: Aggregate recurring task occurrences, annotate status, and return a schedule view.
        raise NotImplementedError("TODO: implement group occurrence listing")

    def get_group_calendar(self, *, group_id: str) -> None:
        """Return the group-level calendar overview."""
        # TODO: Stitch together group tasks, shared events, and upcoming reminders into a single payload.
        raise NotImplementedError("TODO: implement group calendar retrieval")

    def delete_recurring_task(self, *, task_id: str) -> None:
        """Remove a recurring task and its future occurrences."""
        # TODO: Cancel outstanding occurrences, update sync state, and log the deletion.
        raise NotImplementedError("TODO: implement recurring task deletion")

    def consolidate_to_in_app_calendar(self, *, user_id: str) -> None:
        """Ensure the user has a dedicated in-app calendar and backfill missing events."""
        # TODO: Create or locate the personal calendar, backfill events from tasks, and sync metadata.
        raise NotImplementedError("TODO: implement in-app calendar consolidation")
