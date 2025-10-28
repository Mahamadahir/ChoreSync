"""Domain entity definitions for ChoreSync."""


class User:
    """Represents a platform user with identity and notification preferences."""
    # TODO: Define fields and validation rules for User domain entity.


class Group:
    """Represents a household or team coordinating chores."""
    # TODO: Describe attributes (name, owner, reassignment policy, etc.).


class Task:
    """Describes a chore scheduled for a group with optional recurrence."""
    # TODO: Capture task metadata, scheduling data, and ownership details.


class Calendar:
    """Represents an external or in-app calendar source associated with a user."""
    # TODO: Specify provider origin, linkage to user, and sync configuration.


class Event:
    """Represents a calendar event produced from a task or external sync."""
    # TODO: Define event identifiers, timing, and relationship to tasks.


class RecurringTaskOccurrence:
    """Concrete scheduled instance of a recurring task."""
    # TODO: Outline occurrence timing, completion status, and references.


class Message:
    """Represents a chat message exchanged among group members."""
    # TODO: Capture sender, group, timestamps, and message body details.


class MessageReceipt:
    """Tracks per-user read status for a message."""
    # TODO: Model association between message and recipient with read metadata.


class TaskSwap:
    """Captures a swap request between two members for a task."""
    # TODO: Store initiator, target, decision state, and reasoning fields.


class Notification:
    """Represents an in-app notification dispatched to a user."""
    # TODO: Define notification type taxonomy, payload metadata, and lifecycle states.


class TaskProposal:
    """Captures a proposed chore awaiting group approval."""
    # TODO: Include proposal content, recurrence hints, and voting thresholds.


class TaskPreference:
    """Represents a member's preference toward a given task."""
    # TODO: Map user sentiment (avoid/neutral/prefer) to tasks or proposals.


class TaskVote:
    """Represents a member's vote for a specific task decision."""
    # TODO: Record vote outcomes and timestamps for auditing.


class ExternalCredential:
    """Stores provider-specific credential handles for calendar sync."""
    # TODO: Structure encrypted credential references and provider metadata.


class GroupCalendar:
    """Represents the aggregate calendar for a group."""
    # TODO: Track associated tasks, shared events, and visibility rules.


class SyncedEvent:
    """Tracks linkage between an in-app event and an external provider copy."""
    # TODO: Maintain provider event identifiers and sync reconciliation data.
