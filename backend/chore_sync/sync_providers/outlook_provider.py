"""Outlook Calendar provider integration."""
from __future__ import annotations

from dataclasses import dataclass

from chore_sync.services.sync_providers.base import CalendarProvider


@dataclass
class OutlookCalendarProvider(CalendarProvider):
    """Wraps Microsoft Graph calendar operations via OutlookCalendarService."""

    def create_task_event(self, task_occurrence) -> str | None:
        from chore_sync.services.outlook_calendar_service import OutlookCalendarService
        from chore_sync.models import Event, Calendar
        user = task_occurrence.assigned_to
        cal = Calendar.objects.filter(user=user, provider="microsoft", is_task_writeback=True).first()
        if not cal:
            return None
        ev = Event.objects.create(
            calendar=cal,
            user=user,
            title=task_occurrence.template.name,
            start=task_occurrence.deadline,
            end=task_occurrence.deadline,
            source="task",
            task_occurrence=task_occurrence,
        )
        try:
            svc = OutlookCalendarService(user)
            svc.push_created_event(ev)
        except Exception:
            pass
        return ev.external_id

    def update_task_event(self, task_occurrence) -> None:
        from chore_sync.services.outlook_calendar_service import OutlookCalendarService
        from chore_sync.models import Event
        ev = Event.objects.filter(task_occurrence=task_occurrence).first()
        if not ev:
            return
        try:
            svc = OutlookCalendarService(task_occurrence.assigned_to)
            svc.push_updated_event(ev)
        except Exception:
            pass

    def delete_task_event(self, task_occurrence) -> None:
        from chore_sync.services.outlook_calendar_service import OutlookCalendarService
        from chore_sync.models import Event
        ev = Event.objects.filter(task_occurrence=task_occurrence).first()
        if not ev:
            return
        try:
            svc = OutlookCalendarService(task_occurrence.assigned_to)
            svc.push_deleted_event(ev)
        except Exception:
            pass
        ev.delete()
