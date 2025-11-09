"""Guest and visitor access management services."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GuestAccessService:
    """Handles temporary access for visitors, contractors, or short-term helpers."""

    def create_guest_invite(self, *, host_id: str, group_id: str, guest_details: dict) -> None:
        """Issue a guest invite with scoped permissions and expiration."""
        # TODO: Generate secure tokens, persist invite metadata, and send onboarding instructions.
        raise NotImplementedError("TODO: implement guest invite creation")

    def revoke_guest_access(self, *, invite_id: str, actor_id: str) -> None:
        """Terminate guest access immediately."""
        # TODO: Invalidate tokens, remove active sessions, and record removal reasons.
        raise NotImplementedError("TODO: implement guest access revocation")

    def list_guest_sessions(self, *, group_id: str) -> None:
        """List active guest sessions and roles."""
        # TODO: Query session store, join membership context, and surface compliance data.
        raise NotImplementedError("TODO: implement guest session listing")

    def convert_guest_to_member(self, *, guest_id: str, group_id: str, onboarding_payload: dict) -> None:
        """Upgrade a guest into a full member profile."""
        # TODO: Validate consent, create AccountService identities, and migrate permissions.
        raise NotImplementedError("TODO: implement guest-to-member conversion")

    def apply_guest_limits(self, *, guest_id: str) -> None:
        """Enforce throttling and capability limits for guest accounts."""
        # TODO: Centralize rate limits, update policy decisions, and coordinate with Nudge engine.
        raise NotImplementedError("TODO: implement guest capability enforcement")
