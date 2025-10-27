"""Domain entity definitions for ChoreSync."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class User:
    """Represents a platform user with identity and notification preferences."""
    id: str
    email: str
    display_name: str
    timezone: str
    notification_channels: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Group:
    """Represents a household or team coordinating chores."""
    id: str
    name: str
    owner_id: str
    reassignment_rule: str
    reassignment_period: float | None = None


@dataclass(slots=True)
class Task:
    """Describes a chore scheduled for a group with optional recurrence."""
    id: str
    name: str
    details: str
    group_id: str
    created_by: str
    assigned_to: str | None
    due_at: datetime
    estimated_hours: float
    recurrence: str
    recurrence_interval: int


@dataclass(slots=True)
class Calendar:
    """Represents an external or in-app calendar source associated with a user."""
    id: str
    user_id: str
    origin: str
    display_name: str
    external_id: str | None
    push_enabled: bool


@dataclass(slots=True)
class Event:
    """Represents a calendar event produced from a task or external sync."""
    id: str
    calendar_id: str
    title: str
    description: str
    start: datetime
    duration_hours: float
    source_task_id: str | None = None


@dataclass(slots=True)
class RecurringTaskOccurrence:
    """Concrete scheduled instance of a recurring task."""
    id: str
    task_id: str
    start: datetime
    completed: bool
    completed_at: datetime | None = None


@dataclass(slots=True)
class Message:
    """Represents a chat message exchanged among group members."""
    id: str
    group_id: str
    sender_id: str
    body: str
    sent_at: datetime


@dataclass(slots=True)
class MessageReceipt:
    """Tracks per-user read status for a message."""
    message_id: str
    recipient_id: str
    read_at: datetime | None = None


@dataclass(slots=True)
class TaskSwap:
    """Captures a swap request between two members for a task."""
    id: str
    task_id: str
    from_user_id: str
    to_user_id: str
    accepted: bool | None
    reason: str | None
    created_at: datetime
    responded_at: datetime | None = None


@dataclass(slots=True)
class Notification:
    """Represents an in-app notification dispatched to a user."""
    id: str
    recipient_id: str
    type: str
    message: str
    created_at: datetime
    read_at: datetime | None = None


@dataclass(slots=True)
class TaskProposal:
    """Captures a proposed chore awaiting group approval."""
    id: str
    name: str
    details: str
    group_id: str
    proposed_by_id: str
    due_at: datetime
    recurrence: str
    recurrence_interval: int
    created_at: datetime
    approved_at: datetime | None = None


@dataclass(slots=True)
class TaskPreference:
    """Represents a member's preference toward a given task."""
    id: str
    user_id: str
    task_id: str
    preference: int  # e.g. -1 = avoid, 0 = neutral, 1 = prefer


@dataclass(slots=True)
class TaskVote:
    """Represents a member's vote for a specific task decision."""
    id: str
    task_id: str
    voter_id: str
    vote: bool
    created_at: datetime


@dataclass(slots=True)
class ExternalCredential:
    """Stores provider-specific credential handles for calendar sync."""
    id: str
    user_id: str
    provider: str
    secret_reference: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class GroupCalendar:
    """Represents the aggregate calendar for a group."""
    id: str
    group_id: str
    task_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SyncedEvent:
    """Tracks linkage between an in-app event and an external provider copy."""
    id: str
    event_id: str
    calendar_id: str
    provider_event_id: str
    provider: str
