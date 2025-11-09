"""Placeholder tests for GuestAccessService methods."""
from __future__ import annotations

import pytest

from chore_sync.services.guest_access_service import GuestAccessService


def test_create_guest_invite_todo() -> None:
    """GuestAccessService.create_guest_invite should issue invites."""
    pytest.skip("TODO: add assertions for GuestAccessService.create_guest_invite")


def test_revoke_guest_access_todo() -> None:
    """GuestAccessService.revoke_guest_access should terminate permissions."""
    pytest.skip("TODO: add assertions for GuestAccessService.revoke_guest_access")


def test_list_guest_sessions_todo() -> None:
    """GuestAccessService.list_guest_sessions should return active guests."""
    pytest.skip("TODO: add assertions for GuestAccessService.list_guest_sessions")


def test_convert_guest_to_member_todo() -> None:
    """GuestAccessService.convert_guest_to_member should upgrade accounts."""
    pytest.skip("TODO: add assertions for GuestAccessService.convert_guest_to_member")


def test_apply_guest_limits_todo() -> None:
    """GuestAccessService.apply_guest_limits should enforce throttles."""
    pytest.skip("TODO: add assertions for GuestAccessService.apply_guest_limits")
