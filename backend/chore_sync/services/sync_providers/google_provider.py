from __future__ import annotations

import datetime
import logging
from typing import Optional

from django.utils import timezone

from chore_sync.services.sync_providers.base import CalendarProvider

logger = logging.getLogger(__name__)


class GoogleCalendarProvider(CalendarProvider):
    """
    Writeback provider for Google Calendar.

    Finds the user's `is_task_writeback` Google calendar and pushes task events
    to it using GoogleCalendarService.
    """

    def _get_writeback_calendar(self):
        from chore_sync.models import Calendar
        return (
            Calendar.objects.filter(
                user=self.user,
                provider="google",
                is_task_writeback=True,
            )
            .first()
        )

    def _get_service(self):
        from chore_sync.services.google_calendar_service import GoogleCalendarService
        return GoogleCalendarService(user=self.user)

    def _build_task_event_body(self, task_occurrence) -> dict:
        template = task_occurrence.template
        deadline: datetime.datetime = task_occurrence.deadline
        start_dt = deadline - datetime.timedelta(hours=1)
        return {
            "summary": f"[Task] {template.name}",
            "description": template.description or "",
            "start": {
                "dateTime": start_dt.astimezone(datetime.timezone.utc).isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": deadline.astimezone(datetime.timezone.utc).isoformat(),
                "timeZone": "UTC",
            },
        }

    def create_task_event(self, task_occurrence) -> Optional[str]:
        cal = self._get_writeback_calendar()
        if not cal:
            return None
        from chore_sync.models import Event
        ev = Event.objects.create(
            calendar=cal,
            title=f"[Task] {task_occurrence.template.name}",
            description=task_occurrence.template.description or "",
            start=task_occurrence.deadline - datetime.timedelta(hours=1),
            end=task_occurrence.deadline,
            source="task",
            blocks_availability=False,
            task_occurrence=task_occurrence,
        )
        try:
            svc = self._get_service()
            external_id = svc.push_created_event(ev)
            return external_id or None
        except Exception:
            logger.exception(
                "GoogleCalendarProvider: failed to push task event for occurrence %s",
                task_occurrence.id,
            )
            return None

    def update_task_event(self, task_occurrence) -> None:
        from chore_sync.models import Event
        ev = Event.objects.filter(task_occurrence=task_occurrence, source="task").first()
        if not ev:
            return
        ev.title = f"[Task] {task_occurrence.template.name}"
        ev.description = task_occurrence.template.description or ""
        ev.start = task_occurrence.deadline - datetime.timedelta(hours=1)
        ev.end = task_occurrence.deadline
        ev.save(update_fields=["title", "description", "start", "end"])
        try:
            svc = self._get_service()
            svc.push_updated_event(ev)
        except Exception:
            logger.exception(
                "GoogleCalendarProvider: failed to update task event for occurrence %s",
                task_occurrence.id,
            )

    def delete_task_event(self, task_occurrence) -> None:
        from chore_sync.models import Event
        evs = Event.objects.filter(task_occurrence=task_occurrence, source="task")
        for ev in evs:
            if ev.external_event_id and ev.calendar:
                try:
                    svc = self._get_service()
                    creds = svc._load_credentials()
                    if creds:
                        from googleapiclient.discovery import build
                        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
                        cal_id = ev.calendar.external_id or "primary"
                        service.events().delete(
                            calendarId=cal_id,
                            eventId=ev.external_event_id,
                        ).execute()
                except Exception:
                    logger.exception(
                        "GoogleCalendarProvider: failed to delete task event %s for occurrence %s",
                        ev.id,
                        task_occurrence.id,
                    )
            ev.delete()