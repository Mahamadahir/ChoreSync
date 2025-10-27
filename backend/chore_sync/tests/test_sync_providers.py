"""Placeholder tests for calendar sync provider adapters."""
from __future__ import annotations

import pytest

from chore_sync.sync_providers.google_provider import GoogleCalendarProvider
from chore_sync.sync_providers.apple_provider import AppleCalendarProvider
from chore_sync.sync_providers.outlook_provider import OutlookCalendarProvider


# Google provider

def test_google_list_calendars_todo() -> None:
    """GoogleCalendarProvider.list_calendars should enumerate calendars."""
    pytest.skip("TODO: add assertions for GoogleCalendarProvider.list_calendars")


def test_google_pull_events_todo() -> None:
    """GoogleCalendarProvider.pull_events should fetch delta events."""
    pytest.skip("TODO: add assertions for GoogleCalendarProvider.pull_events")


def test_google_push_events_todo() -> None:
    """GoogleCalendarProvider.push_events should upsert events."""
    pytest.skip("TODO: add assertions for GoogleCalendarProvider.push_events")


def test_google_revoke_credentials_todo() -> None:
    """GoogleCalendarProvider.revoke_credentials should revoke access."""
    pytest.skip("TODO: add assertions for GoogleCalendarProvider.revoke_credentials")


# Apple provider

def test_apple_discover_principal_todo() -> None:
    """AppleCalendarProvider.discover_principal should locate CalDAV endpoints."""
    pytest.skip("TODO: add assertions for AppleCalendarProvider.discover_principal")


def test_apple_pull_events_todo() -> None:
    """AppleCalendarProvider.pull_events should fetch CalDAV changes."""
    pytest.skip("TODO: add assertions for AppleCalendarProvider.pull_events")


def test_apple_push_events_todo() -> None:
    """AppleCalendarProvider.push_events should upload iCalendar payloads."""
    pytest.skip("TODO: add assertions for AppleCalendarProvider.push_events")


def test_apple_renew_session_todo() -> None:
    """AppleCalendarProvider.renew_session should refresh credentials."""
    pytest.skip("TODO: add assertions for AppleCalendarProvider.renew_session")


# Outlook provider

def test_outlook_list_calendars_todo() -> None:
    """OutlookCalendarProvider.list_calendars should enumerate calendars."""
    pytest.skip("TODO: add assertions for OutlookCalendarProvider.list_calendars")


def test_outlook_pull_events_todo() -> None:
    """OutlookCalendarProvider.pull_events should fetch delta data."""
    pytest.skip("TODO: add assertions for OutlookCalendarProvider.pull_events")


def test_outlook_push_events_todo() -> None:
    """OutlookCalendarProvider.push_events should upsert events."""
    pytest.skip("TODO: add assertions for OutlookCalendarProvider.push_events")


def test_outlook_renew_subscription_todo() -> None:
    """OutlookCalendarProvider.renew_subscription should refresh webhooks."""
    pytest.skip("TODO: add assertions for OutlookCalendarProvider.renew_subscription")
