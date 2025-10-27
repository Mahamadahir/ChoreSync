"""Placeholder tests for calendar API endpoints."""
from __future__ import annotations

import pytest

from chore_sync.api import calendar_router


def test_sync_google_calendar_endpoint_todo() -> None:
    """/calendars/google/sync should kick off Google sync."""
    pytest.skip("TODO: exercise sync_google_calendar_endpoint once implemented")


def test_sync_apple_calendar_endpoint_todo() -> None:
    """/calendars/apple/sync should kick off Apple sync."""
    pytest.skip("TODO: exercise sync_apple_calendar_endpoint once implemented")


def test_sync_outlook_calendar_endpoint_todo() -> None:
    """/calendars/outlook/sync should kick off Outlook sync."""
    pytest.skip("TODO: exercise sync_outlook_calendar_endpoint once implemented")
