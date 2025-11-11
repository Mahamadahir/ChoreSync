"""Domain entity definitions for ChoreSync."""
from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

# TODO(Model Test Ideas):
# - Validation paths: required fields, uniqueness, and custom clean/validator logic.
# - Relationship behavior: foreign-key/many-to-many linkage, cascade delete rules, and reverse lookups.
# - Domain helpers: computed properties or custom methods that encode business rules (e.g., is_overdue, display_name).
# - State transitions: enums/choice fields, status changes, and soft-delete or archival flows.
# - Audit hooks: automatic timestamps, __str__ representations, and signal-driven side effects (notifications, sync events).


class User(AbstractUser):
    """Represents a platform user with identity and notification preferences."""
    # TODO: Add profile fields (display_name, locale, preferred_time_zone), communication preferences,
    # TODO: and soft-delete/audit timestamps; enforce unique email + username constraints and hook into notification routing.
    email = models.EmailField(unique=True)
    groups_joined = models.ManyToManyField(
        'Group',
        through='GroupMembership',
        related_name= 'members',
        blank=True
    )
    username = None
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] #For superuser setup

class Group(models.Model):
    """Represents a household or team coordinating chores."""
    # TODO: Define fields for canonical name, slug, owner/admin references, membership_limit, fairness_policy configuration,
    # TODO: default timezone, and lifecycle timestamps; ensure uniqueness of slug per owner and cascade rules for memberships.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    group_code = models.CharField(max_length=100)
    owner = models.ForeignKey(User,
                              on_delete=models.SET_NULL,
                              null=True,
                              related_name='owned_groups')
    reassignment_rule = models.CharField(
        max_length=50,
        choices=[
            ('on_create', 'Every time a new task is created'),
            ('after_n_tasks', 'After x tasks are created'),
            ('after_n_weeks', 'After x weeks pass'),
            ('monthly', 'Monthly')
        ],
        default= 'on_create'
    )
    reassignment_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text= "Used to store n for n_task and n_weeks"
    )
    last_reassigned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamps of last reassignment'
    )
    def __str__(self):
        return self.group_code

class GroupMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(
        max_length=20,
        choices=[('member', 'Member'), ('moderator', 'Moderator')],
        default='member'
    )

    class Meta:
        unique_together = ('user', 'group')

    def __str__(self):
        return f"{self.user.email} in {self.group.name}"


class Task:
    """Describes a chore scheduled for a group with optional recurrence."""
    # TODO: Capture title/description, linked group, creator, cadence/recurrence pattern, due window, assignee,
    # TODO: effort estimates, status enum, and hooks for analytics/audit timestamps.


class Calendar:
    """Represents an external or in-app calendar source associated with a user."""
    # TODO: Store provider type (google/outlook/internal), owning user, OAuth credential reference, sync window,
    # TODO: default reminder settings, and last_sync timestamps/flags.


class Event:
    """Represents a calendar event produced from a task or external sync."""
    # TODO: Include start/end, recurrence instance identifiers, link to originating task or calendar, provider event ids,
    # TODO: attendee metadata, and status values for cancellation/rescheduling.


class RecurringTaskOccurrence:
    """Concrete scheduled instance of a recurring task."""
    # TODO: Persist foreign key to parent Task recurrence definition, occurrence index/date, assigned member,
    # TODO: completion metadata, and any skip/defer reasons.


class Message:
    """Represents a chat message exchanged among group members."""
    # TODO: Capture sender FK, target group/thread, plaintext/body, optional attachments, delivery timestamps,
    # TODO: and moderation flags (deleted/edited markers).


class MessageReceipt:
    """Tracks per-user read status for a message."""
    # TODO: Associate message + recipient membership, store delivery/read timestamps, reaction payloads,
    # TODO: and unread-count bookkeeping fields.


class TaskSwap:
    """Captures a swap request between two members for a task."""
    # TODO: Persist initiator/target members, task reference, proposed schedule, approval status enum,
    # TODO: justification text, and audit trail for moderator decisions.


class Notification:
    """Represents an in-app notification dispatched to a user."""
    # TODO: Define type identifiers, payload JSON, severity, delivery channel, sent/read timestamps, and expiry policies.


class TaskProposal:
    """Captures a proposed chore awaiting group approval."""
    # TODO: Store proposing member, payload (title, description, suggested cadence), target group, attachment refs,
    # TODO: voting deadline/thresholds, and approval state transitions.


class TaskPreference:
    """Represents a member's preference toward a given task."""
    # TODO: Map member -> task/proposal with preference enum/weight, optional reasons, and tracking for last_updated.


class TaskVote:
    """Represents a member's vote for a specific task decision."""
    # TODO: Link member to proposal/decision, include chosen option, confidence/notes, timestamps,
    # TODO: and uniqueness constraints (one vote per decision per member).


class ExternalCredential:
    """Stores provider-specific credential handles for calendar sync."""
    # TODO: Store user reference, provider identifier, encrypted secret blob/refresh token handle, scopes granted,
    # TODO: and expiration/refresh bookkeeping.


class GroupCalendar:
    """Represents the aggregate calendar for a group."""
    # TODO: Map to owning group, include timezone, sharing rules, linked external calendars, and configuration flags
    # TODO: for color schemes / conflict resolution strategies.


class SyncedEvent:
    """Tracks linkage between an in-app event and an external provider copy."""
    # TODO: Persist mapping between Event and provider event id, sync status, last_synced_at, checksum/hashes,
    # TODO: and drift/conflict resolution metadata.
