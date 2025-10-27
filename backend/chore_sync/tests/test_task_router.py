"""Placeholder tests for task API endpoints."""
from __future__ import annotations

import pytest

from chore_sync.api import task_router


def test_create_task_endpoint_todo() -> None:
    """/tasks POST should delegate to TaskScheduler once implemented."""
    pytest.skip("TODO: exercise create_task_endpoint with a realistic payload")


def test_reassign_overdue_tasks_endpoint_todo() -> None:
    """/tasks/reassign POST should initiate overdue reassignment."""
    pytest.skip("TODO: exercise reassign_overdue_tasks_endpoint once implemented")


def test_generate_recurring_tasks_endpoint_todo() -> None:
    """/tasks/recurrence POST should project recurring tasks."""
    pytest.skip("TODO: exercise generate_recurring_tasks_endpoint once implemented")
