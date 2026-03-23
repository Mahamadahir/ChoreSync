from __future__ import annotations

import datetime
import logging
from typing import Optional

from chore_sync.services.sync_providers.base import CalendarProvider

logger = logging.getLogger(__name__)


class OutlookCalendarProvider(CalendarProvider):
    """
    Writeback provider for Microsoft Outlook / Graph calendar.

    Finds the user's `is_task_writeback` Microsoft calendar and pushes task
    events to it using OutlookCalendarService.
    """

    def _get_writeback_calendar(self):
        from chore_sync.models import Calendar
        return Calendar.objects.filter(
            user=self.user,
            provider="microsoft",
            is_task_writeback=True,
        ).first()

    def _get_service(self):
        from chore_sync.services.outlook_calendar_service import OutlookCalendarService
        return OutlookCalendarService(user=self.user)

    def create_task_event(self, task_occurrence) -> Optional[str]:
        cal = self._get_writeback_calendar()
        if not cal:
            return None
        from chore_sync.models import Event
        deadline: datetime.datetime = task_occurrence.deadline
        ev = Event.objects.create(
            calendar=cal,
            title=f"[Task] {task_occurrence.template.name}",
            description=task_occurrence.template.description or "",
            start=deadline - datetime.timedelta(hours=1),
            end=deadline,
            source="task",
            blocks_availability=False,
            task_occurrence=task_occurrence,
        )
        try:
            svc = self._get_service()
            svc.push_created_event(ev)
            return ev.external_id or str(ev.id)
        except Exception:
            logger.exception(
                "OutlookCalendarProvider: failed to push task event for occurrence %s",
                task_occurrence.id,
            )
            return None

    def update_task_event(self, task_occurrence) -> None:
        from chore_sync.models import Event
        ev = Event.objects.filter(
            task_occurrence=task_occurrence,
            source="task",
            calendar__provider="microsoft",
        ).first()
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
                "OutlookCalendarProvider: failed to update task event for occurrence %s",
                task_occurrence.id,
            )

    def delete_task_event(self, task_occurrence) -> None:
        from chore_sync.models import Event
        evs = Event.objects.filter(
            task_occurrence=task_occurrence,
            source="task",
            calendar__provider="microsoft",
        )
        for ev in evs:
            try:
                svc = self._get_service()
                svc.push_deleted_event(ev)
            except Exception:
                logger.exception(
                    "OutlookCalendarProvider: failed to delete task event %s for occurrence %s",
                    ev.id,
                    task_occurrence.id,
                )
            ev.delete()
