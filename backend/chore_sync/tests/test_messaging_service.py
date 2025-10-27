"""Placeholder tests for MessagingService methods."""
from __future__ import annotations

import pytest

from chore_sync.services.messaging_service import MessagingService


def test_send_message_todo() -> None:
    """MessagingService.send_message should persist and distribute messages."""
    pytest.skip("TODO: add assertions for MessagingService.send_message")


def test_mark_message_read_todo() -> None:
    """MessagingService.mark_message_read should record receipts."""
    pytest.skip("TODO: add assertions for MessagingService.mark_message_read")


def test_fetch_conversation_todo() -> None:
    """MessagingService.fetch_conversation should page history."""
    pytest.skip("TODO: add assertions for MessagingService.fetch_conversation")


def test_broadcast_live_message_todo() -> None:
    """MessagingService.broadcast_live_message should fan out real-time events."""
    pytest.skip("TODO: add assertions for MessagingService.broadcast_live_message")


def test_list_unread_messages_todo() -> None:
    """MessagingService.list_unread_messages should summarize unread counts."""
    pytest.skip("TODO: add assertions for MessagingService.list_unread_messages")
