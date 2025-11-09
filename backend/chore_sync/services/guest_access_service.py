"""Guest and visitor access management services."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GuestAccessService:
    """Handles temporary access for visitors, contractors, or short-term helpers."""

    def create_guest_invite(self, *, host_id: str, group_id: str, guest_details: dict) -> None:
        """Issue a guest invite with scoped permissions and expiration.

        Inputs:
            host_id: Member issuing the invite.
            group_id: Group granting limited access.
            guest_details: Contact info + role/capability settings.
        Output:
            Invite DTO (token, expiry, capabilities).
        TODO: Generate secure tokens, persist invite metadata, enforce quotas, and send onboarding instructions.
        """
        raise NotImplementedError("TODO: implement guest invite creation")

    def revoke_guest_access(self, *, invite_id: str, actor_id: str) -> None:
        """Terminate guest access immediately.

        Inputs:
            invite_id: Identifier for the guest invite or membership.
            actor_id: User performing the revocation.
        Output:
            None. Should log reasons and confirm revocation.
        TODO: Invalidate invite tokens, revoke sessions, update membership state, log removal reasons, and notify stakeholders.
        """
        raise NotImplementedError("TODO: implement guest access revocation")

    def list_guest_sessions(self, *, group_id: str) -> None:
        """List active guest sessions and roles.

        Inputs:
            group_id: Group whose guest access is being audited.
        Output:
            List of guests with capabilities, expiry times, and session info.
        TODO: Query session store + guest membership records, include compliance metadata, and format for dashboards.
        """
        raise NotImplementedError("TODO: implement guest session listing")

    def convert_guest_to_member(self, *, guest_id: str, group_id: str, onboarding_payload: dict) -> None:
        """Upgrade a guest into a full member profile.

        Inputs:
            guest_id: Guest account/membership.
            group_id: Group granting permanent membership.
            onboarding_payload: Profile details/password info.
        Output:
            New member account/membership DTO.
        TODO: Validate consent + identity, create AccountService user if needed, migrate permissions/preferences,
        TODO: and clean up guest records.
        """
        raise NotImplementedError("TODO: implement guest-to-member conversion")

    def apply_guest_limits(self, *, guest_id: str) -> None:
        """Enforce throttling and capability limits for guest accounts.

        Inputs:
            guest_id: Guest membership.
        Output:
            None. Should adjust policy state and log enforcement actions.
        TODO: Compute rate-limit/capability rules, update enforcement store, coordinate with SmartNudgeService for reminders,
        TODO: and notify moderators when limits are exceeded.
        """
        raise NotImplementedError("TODO: implement guest capability enforcement")
