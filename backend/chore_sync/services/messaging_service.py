"""Messaging coordination services for ChoreSync."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class MessagingService:
    """Handles group chat, read receipts, and real-time fan-out."""

    def send_message(self, *, group_id: str, sender_id: str, body: str) -> None:
        """Persist a message and coordinate delivery.

        TODO: Validate membership, persist the message, attach metadata, and hand the
        payload to the delivery pipeline for real-time fan-out.
        """
        raise NotImplementedError("TODO: implement message send flow")

    def mark_message_read(self, *, message_id: str, reader_id: str, read_at: datetime) -> None:
        """Record a read receipt for a message.

        TODO: Upsert the receipt entry, update unread counters, and notify the sender that
        the message was consumed.
        """
        raise NotImplementedError("TODO: implement read receipt handling")

    def fetch_conversation(self, *, group_id: str, cursor: str | None) -> None:
        """Retrieve a slice of conversation history for a group.

        TODO: Query the message store with pagination, enrich messages with receipts, and
        return a transport-friendly representation.
        """
        raise NotImplementedError("TODO: implement conversation retrieval")

    def broadcast_live_message(self, *, group_id: str, message_id: str) -> None:
        """Push a freshly stored message to all subscribed members.

        TODO: Resolve websocket channels, serialize the payload, and emit acknowledgements
        for delivery monitoring.
        """
        raise NotImplementedError("TODO: implement live message broadcast")

    def list_unread_messages(self, *, user_id: str) -> None:
        """Summarize unread message counts per group for a user.

        TODO: Aggregate unread receipts, merge with notification settings, and expose a
        dashboard-friendly structure.
        """
        raise NotImplementedError("TODO: implement unread message summary")
