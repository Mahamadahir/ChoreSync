"""Domain entity definitions for ChoreSync."""
import uuid
import secrets
import json
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from cryptography.fernet import Fernet

# TODO(Model Test Ideas):
# - Validation paths: required fields, uniqueness, and custom clean/validator logic.
# - Relationship behavior: foreign-key/many-to-many linkage, cascade delete rules, and reverse lookups.
# - Domain helpers: computed properties or custom methods that encode business rules (e.g., is_overdue, display_name).
# - State transitions: enums/choice fields, status changes, and soft-delete or archival flows.
# - Audit hooks: automatic timestamps, __str__ representations, and signal-driven side effects (notifications, sync events).


class EncryptedJSONField(models.TextField):
    """Stores a JSON-serialisable value encrypted at rest using Fernet symmetric encryption."""

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        fernet = Fernet(settings.FIELD_ENCRYPTION_KEY)
        return json.loads(fernet.decrypt(value.encode()))

    def get_prep_value(self, value):
        if value is None:
            return value
        fernet = Fernet(settings.FIELD_ENCRYPTION_KEY)
        return fernet.encrypt(json.dumps(value).encode()).decode()

    def to_python(self, value):
        if isinstance(value, (dict, list)) or value is None:
            return value
        return value  # already decrypted by from_db_value


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

    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        help_text="Profile photo. Populated from SSO provider on first sign-in.",
    )
    avatar_url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        help_text="External avatar URL (e.g. from Google/Microsoft). "
                  "Used when no uploaded avatar is present.",
    )

    def get_avatar_url(self, request=None) -> str | None:
        """Return the best available avatar URL, or None."""
        if self.avatar:
            url = self.avatar.url
            if request:
                return request.build_absolute_uri(url)
            return url
        if self.avatar_url:
            return self.avatar_url
        return None

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
    expires_at = models.DateTimeField(null=True, blank=True)
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

    GROUP_TYPE_CHOICES = [
        ('flatshare', 'Flat Share'),
        ('family',    'Family'),
        ('work_team', 'Work Team'),
        ('custom',    'Custom'),
    ]
    group_type = models.CharField(
        max_length=20,
        choices=GROUP_TYPE_CHOICES,
        default='custom',
        help_text=(
            "Determines join behaviour and invite-UI role labels. "
            "flatshare: everyone joins as moderator. "
            "family/work_team/custom: owner chooses role per invite."
        ),
    )
    task_proposal_voting_required = models.BooleanField(
        default=False,
        help_text=(
            "When True, only moderators can create tasks directly. "
            "Members must submit suggestions which moderators approve or reject."
        ),
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
            ('weekly', 'Weekly on the same day'),
            ('monthly', 'Monthly on the same date'),
            ('every_n_days', 'After x days'),
            ('custom', 'Custom'),
        ],
        default='none',
    )
    days_of_week = models.JSONField(
        null=True,
        blank=True,
        help_text="List of weekday abbreviations (['mon','wed','fri']) for custom recurrence.",
    )
    difficulty = models.PositiveIntegerField(
        default=1,
        help_text="Relative difficulty level of the task (for weighted assignment).",
    )
    estimated_mins = models.PositiveIntegerField(default=30)
    category = models.CharField(
        choices=[
            ('cleaning', 'Cleaning'),
            ('cooking', 'Cooking'),
            ('laundry', 'Laundry'),
            ('maintenance', 'Maintenance'),
            ('other', 'Other'),
        ],
        default='other',
        max_length=20,
    )
    recur_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Used to store n for n_days",
    )
    next_due = models.DateTimeField()
    active = models.BooleanField(default=True)
    recur_end = models.DateField(
        null=True,
        blank=True,
        help_text="Optional date after which no new occurrences are generated.",
    )
    photo_proof_required = models.BooleanField(
        default=False,
        help_text="If True, the assignee must upload a photo when marking this task complete.",
    )

    # Task details
    name = models.CharField(max_length=100)
    details = models.TextField(blank=True)

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
        if self.recurring_choice == 'every_n_days' and not self.recur_value:
            raise ValidationError("Please provide a recur_value for every_n_days recurrence.")
        if self.recurring_choice == 'custom' and not self.days_of_week:
            raise ValidationError("Please provide days_of_week for custom recurrence.")


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
    status_choices = [
        ('suggested', 'Suggested'),
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('snoozed', 'Snoozed'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
        ('reassigned', 'Reassigned'),
        ('cancelled', 'Cancelled'),  # terminal state when parent template is soft-deleted
    ]
    status = models.CharField(
        choices=status_choices,
        max_length=20,
        default='suggested',
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    snoozed_until = models.DateTimeField(null=True, blank=True)
    snooze_count = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(2)]
    )
    original_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name='originally_assigned_tasks',
        on_delete=models.SET_NULL,
        blank=True,
    )
    reassignment_reason = models.CharField(
        choices=[
            ('swap', 'Swap'),
            ('emergency', 'Emergency'),
            ('system', 'System Rebalance')
        ],
        null=True,
        blank=True,
        max_length=20,
    )

    points_earned = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the 24-hour deadline reminder was last sent for this occurrence.",
    )
    reminder_3h_sent = models.BooleanField(
        default=False,
        help_text="Whether the 3-hour-before reminder has been sent.",
    )
    reminder_due_sent = models.BooleanField(
        default=False,
        help_text="Whether the at-due-time reminder has been sent.",
    )

    photo_proof = models.ImageField(
        upload_to='task_proofs/',
        null=True,
        blank=True,
        help_text="Optional photo proof of task completion.",
    )

    # Pre-assignment suggestion fields
    suggestion_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the pre-assignment suggestion notification expires (auto-assigns after this).",
    )
    suggestion_declined_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of user IDs who declined this suggestion (used for fallback assignment).",
    )

    class Meta:
        unique_together = ('template', 'deadline')
        ordering = ['deadline']
        constraints = [
            models.CheckConstraint(
                check=Q(snooze_count__lte=2),
                name='snooze_count_max_2',
            )
        ]


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
        choices=PROVIDER_CHOICES
    )

    secret = EncryptedJSONField(
        help_text="Fernet-encrypted JSON blob of OAuth2 tokens"
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
    push_enabled = models.BooleanField(
        default=True,
        help_text="If False, skip pushing updates to this external calendar.",
    )

    is_task_writeback = models.BooleanField(
        default=False,
        help_text="If True, task occurrences assigned to this user are written back to this calendar.",
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


class GoogleCalendarSync(models.Model):
    calendar = models.OneToOneField(
        Calendar,
        on_delete=models.CASCADE,
        related_name='google_sync',
    )
    sync_token = models.CharField(max_length=512, null=True, blank=True)
    checkpoint_date = models.DateField(
        null=True, blank=True,
        help_text="Furthest date processed during initial back-fill; resume point on restart.",
    )
    active_task_id = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="Celery task ID of the running initial sync — prevents double-queueing.",
    )
    channel_id = models.CharField(max_length=255, null=True, blank=True)
    resource_id = models.CharField(max_length=255, null=True, blank=True)
    watch_expires_at = models.DateTimeField(null=True, blank=True)
    webhook_token = models.CharField(max_length=255, null=True, blank=True)
    paused = models.BooleanField(
        default=False,
        help_text="True while initial sync is running; suppresses concurrent webhook syncs.",
    )
    oauth_writable = models.BooleanField(
        default=False,
        help_text="Cached from Google accessRole — True if owner or writer.",
    )

    class Meta:
        verbose_name = "Google Calendar Sync State"
        verbose_name_plural = "Google Calendar Sync States"

    def __str__(self):
        return f"GoogleCalendarSync({self.calendar})"


class OutlookCalendarSync(models.Model):
    calendar = models.OneToOneField(
        Calendar,
        on_delete=models.CASCADE,
        related_name='outlook_sync',
    )
    delta_link = models.TextField(null=True, blank=True)
    subscription_id = models.CharField(max_length=255, null=True, blank=True)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Outlook Calendar Sync State"
        verbose_name_plural = "Outlook Calendar Sync States"

    def __str__(self):
        return f"OutlookCalendarSync({self.calendar})"


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
    external_etag = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Provider etag for conflict detection.",
    )
    external_updated = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last updated timestamp from provider (ISO).",
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

    def default_swap_expiry():
        return timezone.now() + timedelta(hours=48)

    expires_at = models.DateTimeField(default=default_swap_expiry)
    swap_type = models.CharField(
        choices=[
            ('direct_swap', 'Direct swap'),
            ('open_request', 'Open request'),
            ('emergency', 'Emergency reassignment'),
            ('system_rebalance', 'System rebalance'),
        ],
        default='direct_swap',
        max_length=20,
    )
    counterpart_task = models.ForeignKey(
        TaskOccurrence,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='counterpart_swaps',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Swap for {self.task} (status={self.status})"


class TaskProposal(models.Model):
    """Captures a suggested chore awaiting moderator approval."""

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
        help_text="User who submitted this suggestion (may be null if deleted).",
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
        null=True,
        blank=True,
        related_name='proposals',
        help_text="The TaskTemplate created when this proposal was approved (null until approved).",
    )

    # ── Payload fields ──────────────────────────────────────────────────
    proposed_payload = models.JSONField(
        default=dict,
        help_text=(
            "Full task details as submitted by the proposer — frozen after creation. "
            "Keys mirror TaskTemplate fields: name, category, difficulty, estimated_mins, "
            "recurring_choice, recur_value, days_of_week, next_due, details."
        ),
    )

    approved_payload = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Moderator-edited task details. Null means approved as-is. "
            "When set, diff against proposed_payload is the audit log."
        ),
    )

    # ── Decision metadata ───────────────────────────────────────────────
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_proposals',
        help_text="Moderator who approved or rejected this proposal.",
    )

    approval_note = models.TextField(
        blank=True,
        default='',
        help_text="Moderator's note explaining edits or rejection reason.",
    )

    reason = models.TextField(
        blank=True,
        help_text="Proposer's explanation for why this task should be added.",
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

    @property
    def effective_payload(self) -> dict:
        """The payload that was (or would be) used to create the template."""
        return self.approved_payload if self.approved_payload else self.proposed_payload

    @property
    def payload_diff(self) -> dict:
        """Fields changed by the moderator: {field: {from: x, to: y}}. Empty if no edits."""
        if not self.approved_payload:
            return {}
        diff = {}
        for key, approved_val in self.approved_payload.items():
            proposed_val = self.proposed_payload.get(key)
            if proposed_val != approved_val:
                diff[key] = {'from': proposed_val, 'to': approved_val}
        return diff

    def __str__(self):
        name = self.proposed_payload.get('name', f'Proposal #{self.pk}')
        return f"Proposal '{name}' in {self.group.name} [{self.state}]"


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

    title = models.CharField(max_length=255, default = '')
    action_url = models.CharField(max_length=255, blank=True, default='', help_text="Optional deep-link path or URL for this notification.")
    sent_at = models.DateTimeField(default=timezone.now)


    TYPE_CHOICES = [
        ('task_assigned', 'Task assigned'),
        ('task_swap', 'Task swap'),
        ('group_invite', 'Group invite'),
        ('task_proposal', 'Task proposal'),
        ('message', 'Message'),
        ('deadline_reminder', 'Deadline reminder'),
        ('emergency_reassignment', 'Emergency reassignment'),
        ('badge_earned', 'Badge earned'),
        ('marketplace_claim', 'Marketplace claim'),
        ('suggestion_pattern', 'Smart suggestion: pattern'),
        ('suggestion_availability', 'Smart suggestion: availability'),
        ('suggestion_preference', 'Smart suggestion: preference'),
        ('suggestion_streak', 'Smart suggestion: streak'),  # emitted by SmartSuggestionService
        # suggestion_fairness intentionally omitted — backend method is not yet implemented
        ('calendar_sync_complete', 'Calendar sync complete'),  # emitted by background sync tasks
        # Legacy — declared in old schema but not currently emitted; kept for data compatibility
        ('task_suggestion', 'Task pre-assignment suggestion'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )

    type = models.CharField(
        max_length=50,
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
    task_swap = models.ForeignKey(
        'TaskSwap',
        on_delete=models.SET_NULL,
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


class UserStats(models.Model):
    """Aggregated statistics for a user, updated periodically."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stats',
    )
    household = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='member_stats',
    )
    current_streak_days = models.PositiveIntegerField(default=0)
    longest_streak_days = models.PositiveIntegerField(default=0)

    total_tasks_completed = models.PositiveIntegerField(default=0)
    total_points = models.PositiveIntegerField(default=0)

    tasks_completed_this_week = models.PositiveIntegerField(default=0)
    tasks_completed_this_month = models.PositiveIntegerField(default=0)

    on_time_completion_rate = models.FloatField(default=0.0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'household')

class Badge(models.Model):
    """Represents an earned badge for a user."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    emoji = models.CharField(max_length=8, blank=True, help_text="Single emoji displayed in UI")
    icon_url = models.URLField(blank=True)
    criteria = models.JSONField(help_text="e.g. {'streak_days': 30}")
    points_value = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    """Association of a badge earned by a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='badges',
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name='earned_by',
    )
    household = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='badges',
    )
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge', 'household')


class MarketplaceListing(models.Model):
    """A task occurrence listed on the group marketplace for any member to claim."""

    task_occurrence = models.OneToOneField(
        TaskOccurrence,
        on_delete=models.CASCADE,
        related_name='marketplace_listing',
    )
    listed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='marketplace_listings',
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='marketplace_listings',
    )
    bonus_points = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['expires_at']

    def __str__(self):
        return f"MarketplaceListing({self.task_occurrence}, bonus={self.bonus_points})"


class NotificationPreference(models.Model):
    """Per-user configuration for which notification types to receive and quiet hours."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_prefs',
    )

    # Per-type opt-out flags (True = receive, False = suppress)
    deadline_reminders   = models.BooleanField(default=True)
    task_assigned        = models.BooleanField(default=True)
    task_swap            = models.BooleanField(default=True)
    emergency_reassign   = models.BooleanField(default=True)
    badge_earned         = models.BooleanField(default=True)
    marketplace_activity = models.BooleanField(default=True)
    smart_suggestions    = models.BooleanField(default=True)

    # Quiet hours (evaluated in the user's own timezone stored on User.timezone)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_start         = models.TimeField(null=True, blank=True)  # e.g. 22:00
    quiet_end           = models.TimeField(null=True, blank=True)  # e.g. 08:00

    class Meta:
        verbose_name = 'notification preference'

    def __str__(self):
        return f"NotificationPreference(user={self.user_id})"


class TaskAssignmentHistory(models.Model):
    """Immutable log of every task assignment event."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_history',
    )
    task_template = models.ForeignKey(
        'TaskTemplate',
        on_delete=models.SET_NULL,
        null=True,
        related_name='assignment_history',
    )
    task_occurrence = models.ForeignKey(
        'TaskOccurrence',
        on_delete=models.CASCADE,
        related_name='assignment_history',
    )
    assigned_at     = models.DateTimeField(auto_now_add=True)
    completed       = models.BooleanField(default=False)
    completed_at    = models.DateTimeField(null=True, blank=True)
    was_swapped     = models.BooleanField(default=False)
    was_emergency   = models.BooleanField(default=False)
    was_marketplace = models.BooleanField(default=False)
    score_breakdown = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            'Per-candidate pipeline scores at assignment time. '
            'Keys: winner_id (str), candidates (list of dicts with '
            'user_id, username, stage1_score, pref_multiplier, '
            'affinity_multiplier, calendar_penalty, final_score). '
            'Null for rows created outside the pipeline (swaps, emergency, marketplace).'
        ),
    )

    class Meta:
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['user', 'task_template', 'assigned_at']),
        ]

    def __str__(self):
        return f"TaskAssignmentHistory(user={self.user_id}, occurrence={self.task_occurrence_id})"


class ChatbotSession(models.Model):
    """Stores per-user chatbot conversation history and pending action state."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chatbot_sessions',
    )
    # Messages passed to Ollama: [{"role": "user"|"assistant", "content": "..."}]
    messages = models.JSONField(default=list)
    # Pending multi-turn action: e.g. {"intent": "CANT_DO_TASK", "occurrence_id": 42}
    pending_action = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_active']

    def __str__(self):
        return f"ChatbotSession(user={self.user_id}, messages={len(self.messages)})"


class UserPushToken(models.Model):
    """Stores Expo push tokens so the backend can deliver notifications when the app is backgrounded."""

    PLATFORM_CHOICES = [('ios', 'iOS'), ('android', 'Android')]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_tokens',
    )
    token = models.CharField(max_length=200, unique=True)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='ios')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"PushToken(user={self.user_id}, platform={self.platform})"
