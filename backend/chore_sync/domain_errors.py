from typing import Sequence


class DomainError(Exception):
    """Base for all domain-level errors."""


# --- Auth-related errors ---

class RegistrationError(DomainError):
    """Base for registration-related errors."""


class UsernameAlreadyTaken(RegistrationError):
    """Username is already in use."""
    pass


class EmailAlreadyTaken(RegistrationError):
    """Email is already in use."""
    pass


class InvalidEmail(RegistrationError):
    """Email format or domain is invalid."""
    pass


class WeakPassword(RegistrationError):
    """Password failed strength checks."""

    def __init__(self, messages: Sequence[str]):
        self.messages = list(messages)
        super().__init__("Password does not meet strength requirements.")


class EmailVerificationError(DomainError):
    """Base class for email verification issues."""


class VerificationTokenInvalid(EmailVerificationError):
    """Token does not exist or is malformed."""
    pass


class VerificationTokenExpired(EmailVerificationError):
    """Token is valid but past its expiry time."""
    pass


class VerificationTokenUsed(EmailVerificationError):
    """Token has already been consumed."""
    pass


class InvalidCredentials(DomainError):
    """Wrong username/email/password combination."""
    pass


class InactiveAccount(DomainError):
    """User exists but is inactive."""
    pass


# --- Group / domain behaviour errors ---

class NotGroupMember(DomainError):
    """User is not a member of the target group."""
    pass


class InvalidSwap(DomainError):
    """Swap request is invalid in the current state."""
    pass


class ProposalClosed(DomainError):
    """Proposal is not open for this operation (e.g. already approved/rejected)."""
    pass
