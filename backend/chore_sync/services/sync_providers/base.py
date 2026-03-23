from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class CalendarProvider(ABC):
    """
    Abstract base for calendar providers (Google, Outlook, …).

    Each concrete provider receives the user at construction time and exposes
    the three writeback operations needed by TaskLifecycleService.
    """

    def __init__(self, user):
        self.user = user

    @abstractmethod
    def create_task_event(self, task_occurrence) -> Optional[str]:
        """
        Write a task occurrence as a calendar event on the user's task-writeback
        calendar.  Returns the external_event_id on success, or None on failure.
        """

    @abstractmethod
    def update_task_event(self, task_occurrence) -> None:
        """
        Update an existing calendar event to reflect changes to the task
        (e.g. deadline change, name change).
        """

    @abstractmethod
    def delete_task_event(self, task_occurrence) -> None:
        """
        Delete the calendar event associated with a task occurrence (e.g. on
        reassignment away from this user, or on task cancellation).
        """