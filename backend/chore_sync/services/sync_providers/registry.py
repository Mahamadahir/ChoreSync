from __future__ import annotations

from typing import Optional

from chore_sync.services.sync_providers.base import CalendarProvider


def get_provider(calendar, user=None) -> Optional[CalendarProvider]:
    """
    Return the appropriate CalendarProvider for the given calendar, or None if
    no provider is registered for that calendar's provider type.

    Usage::

        provider = get_provider(calendar)
        if provider:
            provider.create_task_event(occurrence)
    """
    if user is None:
        user = calendar.user

    provider_name = getattr(calendar, "provider", None)

    if provider_name == "internal":
        from chore_sync.services.sync_providers.internal_provider import InternalCalendarProvider
        return InternalCalendarProvider(user=user)

    if provider_name == "google":
        from chore_sync.services.sync_providers.google_provider import GoogleCalendarProvider
        return GoogleCalendarProvider(user=user)

    if provider_name == "microsoft":
        from chore_sync.services.sync_providers.outlook_provider import OutlookCalendarProvider
        return OutlookCalendarProvider(user=user)

    return None


def get_task_writeback_provider(user) -> Optional[CalendarProvider]:
    """
    Return the CalendarProvider for the user's designated task-writeback calendar,
    or None if the user has no task-writeback calendar configured.
    """
    from chore_sync.models import Calendar
    writeback_cal = Calendar.objects.filter(
        user=user,
        is_task_writeback=True,
    ).first()
    if not writeback_cal:
        return None
    return get_provider(writeback_cal, user=user)