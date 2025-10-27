"""Placeholder tests for group API endpoints."""
from __future__ import annotations

import pytest

from chore_sync.api import group_router


def test_create_group_endpoint_todo() -> None:
    """/groups POST should create a group."""
    pytest.skip("TODO: exercise create_group_endpoint once implemented")


def test_invite_group_member_endpoint_todo() -> None:
    """/groups/invite POST should invite a member."""
    pytest.skip("TODO: exercise invite_group_member_endpoint once implemented")


def test_get_assignment_matrix_endpoint_todo() -> None:
    """/groups/{group_id}/assignment-matrix should return assignment data."""
    pytest.skip("TODO: exercise get_assignment_matrix_endpoint once implemented")
