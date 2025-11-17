"""Domain entity definitions for ChoreSync."""
import uuid
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import ForeignKey
from django.db.models.fields import CharField

from tests.test_models import group


# TODO(Model Test Ideas):
# - Validation paths: required fields, uniqueness, and custom clean/validator logic.
# - Relationship behavior: foreign-key/many-to-many linkage, cascade delete rules, and reverse lookups.
# - Domain helpers: computed properties or custom methods that encode business rules (e.g., is_overdue, display_name).
# - State transitions: enums/choice fields, status changes, and soft-delete or archival flows.
# - Audit hooks: automatic timestamps, __str__ representations, and signal-driven side effects (notifications, sync events).


class User(AbstractUser):
    """Represents a platform user with identity and notification preferences."""
    email = models.EmailField(unique=True)
    groups_joined = models.ManyToManyField(
        'Group',
        through='GroupMembership',
        related_name= 'joined_users',
        blank=True
    )

    def __str__(self):
        return self.email or self.username


class Group(models.Model):
    """Represents a household or team coordinating chores."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='Group Name')
    group_code = models.CharField(max_length=100, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL,
                              on_delete=models.SET_NULL,
                              null=True,
                              related_name='owned_groups')
    reassignment_rule = models.CharField(
        max_length=50,
        choices=[
            ('on_create', 'Every time a new task is created'),
            ('after_n_tasks', 'After x tasks are created'),
            ('after_n_weeks', 'After x weeks pass'),
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(
        max_length=20,
        choices=[('member', 'Member'), ('moderator', 'Moderator')],
        default='member'
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')

    def __str__(self):
        return f"{self.user.email} in {self.group.name}"


class TaskTemplate(models.Model):
    """Describes a chore scheduled for a group with optional recurrence."""


    #Recurance resolved here.
    recurring_choice = models.CharField(
        max_length=50,
        choices = [
        ('none', 'No repeat'),
        ('every_n_days', 'After x days'),
    ],
        default= 'none'
    )
    recur_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Used to store n for n_days"
    )
    next_due = models.DateTimeField()
    active = models.BooleanField(default=True)

    #Task details
    name = models.CharField(max_length=100)
    details = models.TextField(blank=True)
    estimated_hours = models.FloatField(default=1.0)

    #ownership of task - Task template not assigned - occurrence is assigned
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tasks',
        help_text="User who created this task"
        )
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        related_name='tasks',
        help_text='Group this task belongs to'
    )

    #history of Task Template
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    #Ensures that recurring tasks have a recurring value and non-recurring tasks don't
    def clean(self):

        if self.recurring_choice == 'none' and self.recur_value:
            raise ValidationError("Recur value should only be set if recurrence is enabled.")
        if self.recurring_choice != 'none' and not self.recur_value:
            raise ValidationError("Please provide a recur_value for repeating tasks.")

    def get_next_due_date(self, from_date=None):
        """Compute the next due date for this task template."""
        from_date = from_date or self.next_due

        recur_value = int(self.recur_value or 0)

        if self.recurring_choice == 'every_n_days' and recur_value > 0:
            return from_date + timedelta(days=recur_value)

        return None
    def __str__(self):
        return f"{self.name} ({self.group.name})"


class TaskOccurrence(models.Model):
    template = models.ForeignKey(
        'TaskTemplate',
        on_delete=models.CASCADE,
        related_name='occurrences'
)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
        help_text="Current assignee for the task"
    )
    deadline = models.DateTimeField()
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('template', 'deadline')
        ordering = ['deadline']

    def __str__(self):
        return f"{self.template.name} on {self.deadline:%Y-%m-%d}"

class Calendar(models.Model):
    """Represents an external or in-app calendar source associated with a user."""

    #user related fields

    PROVIDER_CHOICES = [
        ('google', 'Google Calendar'),
        ('microsoft', 'Microsoft Outlook'),
        ('internal', 'Built-in Calendar'),
    ]

    user = ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name = 'calendars'
    )
    provider = CharField(
        max_length=20,
        choices = PROVIDER_CHOICES,
        default = 'internal'
    )
    external_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="ID used by external provider to identify the calendar",
        default = None
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of the calendar to display in the UI"
    )

    description = models.TextField(
        null=True,
        blank=True,
        help_text="Optional user-provided description for the calendar"
    )

    #credentials
    credential = models.ForeignKey(
        'ExternalCredential',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calendars',
        help_text="OAuth2 credentials used to sync this calendar"
    )
    #Sync details
    sync_enabled = models.BooleanField(default=False)
    back_sync_enabled = models.BooleanField(default=False, help_text="Push app events to external provider?")

    sync_token = models.CharField(
        max_length=512,
        null=True,
        blank=True,
        help_text="Provider-specific sync token for incremental sync"
    )

    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this calendar was last synced"
    )

    sync_window_days = models.PositiveIntegerField(
        default=365,
        help_text="Sync events within X days from now"
    )

    default_reminder_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Default reminder time in minutes before event start"
    )

    timezone = models.CharField(
        max_length=50,
        default="UTC",
        help_text="Timezone identifier"
    )

    color = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Display color for the calendar (if supported by provider)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'provider', 'external_id')
        verbose_name = "Calendar"
        verbose_name_plural = "Calendars"

    def __str__(self):
        return f"{self.user.email} - {self.name or self.provider}"

class Event(models.Model):
    """Represents a calendar event (internal, task-derived, or external)."""

    SOURCE_CHOICES = [
        ('external', 'External calendar event'),
        ('task', 'Generated from a task occurrence'),
        ('manual', 'Manual in-app event'),
    ]

    calendar = models.ForeignKey(
        'Calendar',
        on_delete=models.CASCADE,
        related_name='events'
    )

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='manual',
        help_text="Where this event originated (external feed, task, or manual)."
    )

    # Link back to a task occurrence ONLY if source='task'
    task_occurrence = models.OneToOneField(
        'TaskOccurrence',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='event',
        help_text="Task occurrence that generated this event (if any)."
    )

    # Core timing + display fields
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    start = models.DateTimeField()
    end = models.DateTimeField()

    is_all_day = models.BooleanField(
        default=False,
        help_text="Treat as an all-day event when rendering / syncing."
    )

    # Availability / free-time logic
    blocks_availability = models.BooleanField(
        default=True,
        help_text="If False, this event is ignored when computing free time."
    )

    # External sync metadata
    external_event_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="ID of this event in the external provider's calendar API."
    )
    external_calendar_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Provider's calendar ID at the time of sync (for safety)."
    )

    status = models.CharField(
        max_length=20,
        default='confirmed',
        help_text="confirmed / cancelled / tentative / etc."
    )

    # Debug-only: original provider payload
    raw_payload = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Optional raw provider payload for debugging and edge cases. "
            "Only populated in DEBUG for external events."
        )
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start']

    def __str__(self):
        return self.title

class Message(models.Model):
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages'
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']


class MessageReceipt(models.Model):
    """Per-user read status for a message (simple receipts)."""

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='receipts'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_receipts'
    )
    seen_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the user first read the message (null = not seen yet)."
    )

    class Meta:
        unique_together = ('message', 'user')

class TaskSwap:
    """Captures a swap request between two members for a task."""
    # TODO: Persist initiator/target members, task reference, proposed schedule, approval status enum,
    # TODO: justification text, and audit trail for moderator decisions.
    task = models.ForeignKey(
        TaskOccurrence,
        on_delete=models.CASCADE,
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='swaps_initiated'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='swaps_accepted'
    )
    accepted = models.BooleanField(
        null=True,
    )
    reason = models.TextField(
        blank=True,
        null=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)


class Notification:
    """Represents an in-app notification dispatched to a user."""
    # TODO: Define type identifiers, payload JSON, severity, delivery channel, sent/read timestamps, and expiry policies.
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    NOTIFICATION_CHOICES = [
        ('task_assigned', 'Task assigned'),
        ('task_swap', 'Task Swap'),
        ('group_invite', 'Group Invite'),
    ]
    content = models.TextField()
    read = models.BooleanField(default=False)
    dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)



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


class ExternalCredential(models.Model):
    """
    Stores provider-specific OAuth2 credentials for external calendar sync (Google/Microsoft).
    Each credential represents an OAuth grant from a user to a given provider.
    """

    PROVIDER_CHOICES = [
        ('google', 'Google'),
        ('microsoft', 'Microsoft'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='external_credentials'
    )

    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES
    )

    # Use a JSONField to store tokens. In production, this should be ENCRYPTED.
    # TODO: Encrypt this field before production
    secret = models.JSONField(
        help_text="JSON blob of OAuth2 tokens, including access and refresh tokens"
    )

    # Optional email or identifier for linked account (useful for multi-account support)
    account_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Email of the provider account if available"
    )

    # Space-separated or JSON list of scopes granted
    scopes = models.TextField(
        null=True,
        blank=True,
        help_text="Scopes granted during OAuth login (for debugging or extension)"
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiry datetime of the OAuth2 access token"
    )

    last_refreshed_at = models.DateTimeField(
        auto_now=True,
        help_text="When the token was last refreshed"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "External Credential"
        verbose_name_plural = "External Credentials"
        unique_together = ("user", "provider", "account_email")  # Prevent duplicate credentials

    def __str__(self):
        return f"{self.user.email} - {self.provider} ({self.account_email or 'default'})"

    # Utility: Check if access token is expired
    def is_expired(self) -> bool:
        return self.expires_at and timezone.now() >= self.expires_at

    # Utility: Mark this credential as refreshed
    def mark_refreshed(self, new_secret: dict, new_expires_at):
        self.secret = new_secret
        self.expires_at = new_expires_at
        self.save(update_fields=["secret", "expires_at", "last_refreshed_at"])

class GroupCalendar:
    """Represents the aggregate calendar for a group."""
    # TODO: Map to owning group, include timezone, sharing rules, linked external calendars, and configuration flags
    # TODO: for color schemes / conflict resolution strategies.



