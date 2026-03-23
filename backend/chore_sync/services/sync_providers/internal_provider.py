from __future__ import annotations

import datetime
import logging
from typing import Optional

from chore_sync.services.sync_providers.base import CalendarProvider

logger = logging.getLogger(__name__)


class InternalCalendarProvider(CalendarProvider):
    """
    Writeback provider for the built-in in-app calendar.

    No external API is involved — task occurrences are stored as Event rows on
    the user's internal (provider='internal', is_task_writeback=True) calendar.
    This means every user automatically gets task events in their in-app
    calendar regardless of whether they have connected Google/Outlook.
    """

    def _get_writeback_calendar(self):
        from chore_sync.models import Calendar
        return Calendar.objects.filter(
            user=self.user,
            provider="internal",
            is_task_writeback=True,
        ).first()

    def create_task_event(self, task_occurrence) -> Optional[str]:
        from chore_sync.models import Event
        cal = self._get_writeback_calendar()
        if not cal:
            return None
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
        return str(ev.id)

    def update_task_event(self, task_occurrence) -> None:
        from chore_sync.models import Event
        ev = Event.objects.filter(
            task_occurrence=task_occurrence,
            source="task",
            calendar__provider="internal",
        ).first()
        if not ev:
            return
        ev.title = f"[Task] {task_occurrence.template.name}"
        ev.description = task_occurrence.template.description or ""
        ev.start = task_occurrence.deadline - datetime.timedelta(hours=1)
        ev.end = task_occurrence.deadline
        ev.save(update_fields=["title", "description", "start", "end"])

    def delete_task_event(self, task_occurrence) -> None:
        from chore_sync.models import Event
        Event.objects.filter(
            task_occurrence=task_occurrence,
            source="task",
            calendar__provider="internal",
        ).delete()