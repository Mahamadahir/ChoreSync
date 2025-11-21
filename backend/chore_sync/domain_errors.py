from typing import Sequence


class DomainError(Exception):
    """Base for all domain-level errors."""


# --- Auth-related errors ---

class RegistrationError(DomainError):
    """Base for registration-related errors."""


class UsernameAlreadyTaken(RegistrationError):
    pass


class EmailAlreadyTaken(RegistrationError):
    pass


class WeakPassword(RegistrationError):
    def __init__(self, messages: Sequence[str]):
        self.messages = list(messages)
        super().__init__("Password does not meet strength requirements.")


class InvalidCredentials(DomainError):
    """Wrong username/email/password combination."""


class InactiveAccount(DomainError):
    """User exists but is inactive (if you need that semantics)."""



class NotGroupMember(DomainError):
    pass


class InvalidSwap(DomainError):
    pass


class ProposalClosed(DomainError):
    pass
