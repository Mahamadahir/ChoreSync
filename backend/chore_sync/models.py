"""Domain entity definitions for ChoreSync."""
import uuid
import secrets

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

# TODO(Model Test Ideas):
# - Validation paths: required fields, uniqueness, and custom clean/validator logic.
# - Relationship behavior: foreign-key/many-to-many linkage, cascade delete rules, and reverse lookups.
# - Domain helpers: computed properties or custom methods that encode business rules (e.g., is_overdue, display_name).
# - State transitions: enums/choice fields, status changes, and soft-delete or archival flows.
# - Audit hooks: automatic timestamps, __str__ representations, and signal-driven side effects (notifications, sync events).


class User(AbstractUser):
    """Represents a platform user with identity and notification preferences."""
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        help_text="Preferred timezone for this user",
    )
    groups_joined = models.ManyToManyField(
        'Group',
        through='GroupMembership',
        related_name='joined_users',
        blank=True,
    )

    on_time_streak_days = models.PositiveIntegerField(
        default=0,
        help_text="Consecutive days the user has met all task deadlines.",
    )
    longest_on_time_streak_days = models.PositiveIntegerField(
        default=0,
        help_text="Longest historical on-time streak in days.",
    )
    last_streak_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date on which the streak was last updated.",
    )


    def __str__(self):
        return self.email or self.username

class EmailVerificationToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_verification_tokens',
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=['used_at'])

    @classmethod
    def generate_for_user(cls, user, *, lifetime_hours: int = 24):
        token = secrets.token_urlsafe(32)
        return cls.objects.create(
            user=user,
            token=token,
            expires_at=timezone.now() + timedelta(hours=lifetime_hours),
        )


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=['used_at'])

    @classmethod
    def generate_for_user(cls, user, *, lifetime_hours: int = 1):
        token = secrets.token_urlsafe(32)
        return cls.objects.create(
            user=user,
            token=token,
            expires_at=timezone.now() + timedelta(hours=lifetime_hours),
        )


class EmailLog(models.Model):
    """Store logs of emails sent for auditing."""

    to_address = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    context = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email to {self.to_address} at {self.created_at:%Y-%m-%d %H:%M}"

class Group(models.Model):
    """Represents a household or team coordinating chores."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='Group Name')
    group_code = models.CharField(max_length=100, unique=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_groups',
    )

    reassignment_rule = models.CharField(
        max_length=50,
        choices=[
            ('on_create', 'Every time a new task is created'),
            ('after_n_tasks', 'After x tasks are created'),
            ('after_n_weeks', 'After x weeks pass'),
        ],
        default='on_create',
    )
    reassignment_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Used to store n for n_tasks and n_weeks",
    )
    last_reassigned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp of last reassignment',
    )

    def __str__(self):
        return self.group_code


class GroupMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='members',
    )
    role = models.CharField(
        max_length=20,
        choices=[('member', 'Member'), ('moderator', 'Moderator')],
        default='member',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')

    def __str__(self):
        return f"{self.user.email} in {self.group.name}"



class TaskTemplate(models.Model):
    """Describes a chore scheduled for a group with optional recurrence."""

    IMPORTANCE_CHOICES = [
        ('core', 'Core'),
        ('additional', 'Additional'),
    ]

    importance = models.CharField(
        max_length=20,
        choices=IMPORTANCE_CHOICES,
        default='core',
        help_text=(
            "Core tasks are considered essential for new members; "
            "additional tasks can be bulk-set to neutral on join."
        ),
    )

    # Recurrence
    recurring_choice = models.CharField(
        max_length=50,
        choices=[
            ('none', 'No repeat'),
            ('every_n_days', 'After x days'),
        ],
        default='none',
    )
    recur_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Used to store n for n_days",
    )
    next_due = models.DateTimeField()
    active = models.BooleanField(default=True)

    # Task details
    name = models.CharField(max_length=100)
    details = models.TextField(blank=True)
    estimated_hours = models.FloatField(default=1.0)

    # Ownership
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tasks',
        help_text="User who created this task",
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='tasks',
        help_text='Group this task belongs to',
    )

    # History
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Ensure recurrence fields make sense
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
        TaskTemplate,
        on_delete=models.CASCADE,
        related_name='occurrences',
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
        help_text="Current assignee for the task",
    )
    deadline = models.DateTimeField()
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('template', 'deadline')
        ordering = ['deadline']

    def __str__(self):
        return f"{self.template.name} on {self.deadline:%Y-%m-%d}"


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
        related_name='external_credentials',
    )

    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
    )

    # Use a JSONField to store tokens. In production, this should be ENCRYPTED.
    # TODO: Encrypt this field before production
    secret = models.JSONField(
        help_text="JSON blob of OAuth2 tokens, including access and refresh tokens",
    )

    # Optional email or identifier for linked account (useful for multi-account support)
    account_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Email of the provider account if available",
    )

    # Space-separated or JSON list of scopes granted
    scopes = models.TextField(
        null=True,
        blank=True,
        help_text="Scopes granted during OAuth login (for debugging or extension)",
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiry datetime of the OAuth2 access token",
    )

    last_refreshed_at = models.DateTimeField(
        auto_now=True,
        help_text="When the token was last refreshed",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        verbose_name = "External Credential"
        verbose_name_plural = "External Credentials"
        unique_together = ("user", "provider", "account_email")

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


class Calendar(models.Model):
    """Represents an external or in-app calendar source associated with a user."""

    PROVIDER_CHOICES = [
        ('google', 'Google Calendar'),
        ('microsoft', 'Microsoft Outlook'),
        ('internal', 'Built-in Calendar'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calendars',
    )
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='internal',
    )
    external_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="ID used by external provider to identify the calendar",
        default=None,
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of the calendar to display in the UI",
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Optional user-provided description for the calendar",
    )

    # Credentials
    credential = models.ForeignKey(
        ExternalCredential,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calendars',
        help_text="OAuth2 credentials used to sync this calendar",
    )

    # Sync details
    sync_enabled = models.BooleanField(default=False)
    back_sync_enabled = models.BooleanField(
        default=False,
        help_text="Push app events to external provider?",
    )

    sync_token = models.CharField(
        max_length=512,
        null=True,
        blank=True,
        help_text="Provider-specific sync token for incremental sync",
    )

    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this calendar was last synced",
    )

    sync_window_days = models.PositiveIntegerField(
        default=365,
        help_text="Sync events within X days from now",
    )

    default_reminder_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Default reminder time in minutes before event start",
    )

    timezone = models.CharField(
        max_length=50,
        default="UTC",
        help_text="Timezone identifier",
    )

    color = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Display color for the calendar (if supported by provider)",
    )

    include_in_availability = models.BooleanField(
        default=True,
        help_text="If False, events from this calendar are ignored in free-time computation.",
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
        Calendar,
        on_delete=models.CASCADE,
        related_name='events',
    )

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='manual',
        help_text="Where this event originated (external feed, task, or manual).",
    )

    # Link back to a task occurrence ONLY if source='task'
    task_occurrence = models.OneToOneField(
        TaskOccurrence,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='event',
        help_text="Task occurrence that generated this event (if any).",
    )

    # Core timing + display fields
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    start = models.DateTimeField()
    end = models.DateTimeField()

    is_all_day = models.BooleanField(
        default=False,
        help_text="Treat as an all-day event when rendering / syncing.",
    )

    # Availability / free-time logic
    blocks_availability = models.BooleanField(
        default=True,
        help_text="If False, this event is ignored when computing free time.",
    )

    # External sync metadata
    external_event_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="ID of this event in the external provider's calendar API.",
    )
    external_calendar_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Provider's calendar ID at the time of sync (for safety).",
    )

    status = models.CharField(
        max_length=20,
        default='confirmed',
        help_text="confirmed / cancelled / tentative / etc.",
    )

    # Debug-only: original provider payload
    raw_payload = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Optional raw provider payload for debugging and edge cases. "
            "Only populated in DEBUG for external events."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start']
        indexes = [
            models.Index(fields=['calendar', 'start']),
        ]

    def __str__(self):
        return self.title


class Message(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        sender = self.sender.email if self.sender else "Unknown"
        return f"{sender}: {self.content[:30]}"


class MessageReceipt(models.Model):
    """Per-user read status for a message (simple receipts)."""

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='receipts',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_receipts',
    )
    seen_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the user first read the message (null = not seen yet).",
    )

    class Meta:
        unique_together = ('message', 'user')


class TaskSwap(models.Model):
    """
    Captures a swap request for a task.

    Open-ended: to_user is null when proposed. Any eligible group member can accept it,
    at which point to_user is set and the task's assigned_to is updated in service logic.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    # If the task is deleted, we want the swap gone too.
    task = models.ForeignKey(
        TaskOccurrence,
        on_delete=models.CASCADE,
        related_name='swap_requests',
    )

    # User who created / initiated the swap request
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='swaps_initiated',
        help_text="User who proposed the swap (may be null if user was deleted).",
    )

    # User who eventually accepts the swap (open-ended initially)
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='swaps_accepted',
        help_text="User who accepted the swap (null while pending/open-ended).",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current state of this swap request.",
    )

    reason = models.TextField(
        blank=True,
        null=True,
        help_text="Optional explanation / justification for proposing the swap.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the swap was accepted/rejected/cancelled (if applicable).",
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Swap for {self.task} (status={self.status})"


class TaskProposal(models.Model):
    """Captures a proposed chore awaiting group approval."""

    STATE_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]

    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default='pending',
        help_text="Current approval state of the proposal.",
    )

    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='task_proposals',
        help_text="User who created this proposal (may be null if deleted).",
    )

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='task_proposals',
        help_text="Group this proposal was put forward to.",
    )

    task_template = models.ForeignKey(
        TaskTemplate,
        on_delete=models.SET_NULL,
        null = True,
        blank = True,
        related_name='proposals',
        help_text="The underlying task template being proposed - if the proposal isn't accepted - we'll keep this for history.",
    )

    reason = models.TextField(
        blank=True,
        help_text="Optional explanation for why this task should be added.",
    )

    voting_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When proposal will expire if not decided before this deadline.",
    )

    required_support_ratio = models.FloatField(
        default=0.5,
        help_text="Minimum fraction of supporting votes to approve, once all members have voted.",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the proposal was approved (if applicable).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_open(self) -> bool:
        return self.state == 'pending'

    # Backwards-compatible alias if you already used in_open somewhere
    def in_open(self) -> bool:
        return self.is_open

    def __str__(self):
        return f"Proposal for '{self.task_template.name}' in {self.group.name}"


class TaskVote(models.Model):
    """Represents a member's vote for a specific task decision."""

    VOTE_CHOICES = [
        ('support', 'Support'),
        ('reject', 'Reject'),
        ('abstain', 'Abstain'),
    ]

    proposal = models.ForeignKey(
        TaskProposal,
        on_delete=models.CASCADE,
        related_name='votes',
        help_text="The proposal being voted on.",
    )

    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_votes',
    )

    choice = models.CharField(
        max_length=20,
        choices=VOTE_CHOICES,
        help_text="The member's decision for this proposal.",
    )

    note = models.TextField(
        blank=True,
        help_text="Optional comment or reasoning for the vote.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('proposal', 'voter')
        verbose_name = "Task vote"
        verbose_name_plural = "Task votes"

    def __str__(self):
        return f"{self.voter} voted {self.choice} on {self.proposal_id}"


class TaskPreference(models.Model):
    """Represents a member's preference toward a given task template."""

    PREFERENCE_CHOICES = [
        ('prefer', 'Prefer'),
        ('neutral', 'Neutral'),
        ('avoid', 'Avoid'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_preferences',
    )

    task_template = models.ForeignKey(
        TaskTemplate,
        on_delete=models.CASCADE,
        related_name='preferences',
    )

    preference = models.CharField(
        max_length=20,
        choices=PREFERENCE_CHOICES,
        default='neutral',
    )

    reason = models.TextField(
        blank=True,
        help_text="Optional explanation of this preference.",
    )

    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="When this preference was last changed.",
    )

    class Meta:
        unique_together = ('user', 'task_template')

    def __str__(self):
        return f"{self.user} {self.preference} {self.task_template.name}"

    def weight(self) -> int:
        """Map preference to a simple numeric weight."""
        return {'avoid': -1, 'neutral': 0, 'prefer': 1}[self.preference]


class Notification(models.Model):
    """Generic in-app notification dispatched to a user."""

    TYPE_CHOICES = [
        ('task_assigned', 'Task assigned'),
        ('task_swap', 'Task swap'),
        ('group_invite', 'Group invite'),
        ('task_proposal', 'Task proposal'),
        ('message', 'Message'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )

    type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
    )

    # Generic target fields for deep-linking later
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        help_text="Group this notification relates to (if any).",
    )
    task_occurrence = models.ForeignKey(
        TaskOccurrence,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    task_proposal = models.ForeignKey(
        TaskProposal,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )

    content = models.TextField()

    read = models.BooleanField(default=False)
    dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'read']),
            models.Index(fields=['recipient', 'created_at']),
        ]

    def __str__(self):
        return f"Notification to {self.recipient} ({self.type})"


class GroupCalendar(models.Model):
    """Represents settings for the aggregate calendar for a group."""

    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='calendar_settings',
    )

    timezone = models.CharField(
        max_length=50,
        default="UTC",
        help_text="Timezone used when aggregating the group's calendar.",
    )

    show_member_calendars = models.BooleanField(
        default=True,
        help_text="If True, include members' personal calendars in the group view.",
    )

    show_group_tasks = models.BooleanField(
        default=True,
        help_text="If True, include task-derived events in the group calendar.",
    )

    color = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Optional default color for group events.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Group calendar settings for {self.group.name}"
