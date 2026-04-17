from django.contrib import admin
from . import models
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

# Register all models not already covered
admin.site.register(models.EmailVerificationToken)
admin.site.register(models.PasswordResetToken)
admin.site.register(models.EmailLog)

# -------------------------------------------------------------------
# Group & Membership
# -------------------------------------------------------------------
@admin.register(models.User)
class UserAdmin(DjangoUserAdmin):
    """Admin config for the custom User model."""

    list_display = ("username", "email", "timezone", "is_staff", "is_active")
    search_fields = ("username", "email")
    ordering = ("username",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email", "timezone")}),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )

class GroupMembershipInline(admin.TabularInline):
    model = models.GroupMembership
    extra = 1
    autocomplete_fields = ("user",)


@admin.register(models.Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "group_code", "owner", "reassignment_rule", "reassignment_value")
    search_fields = ("name", "group_code", "owner__email")
    list_filter = ("reassignment_rule",)
    inlines = [GroupMembershipInline]


@admin.register(models.GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "role", "joined_at")
    list_filter = ("role", "group")
    search_fields = ("user__email", "group__name")


# -------------------------------------------------------------------
# Tasks: Template, Occurrence, Preferences, Swaps, Proposals, Votes
# -------------------------------------------------------------------

class TaskOccurrenceInline(admin.TabularInline):
    model = models.TaskOccurrence
    extra = 0
    autocomplete_fields = ("assigned_to",)


@admin.register(models.TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "category", "importance", "difficulty", "recurring_choice", "recur_value", "next_due", "active")
    list_filter = ("active", "recurring_choice", "category", "importance", "group")
    search_fields = ("name", "group__name")
    autocomplete_fields = ("creator", "group")
    inlines = [TaskOccurrenceInline]


@admin.register(models.TaskOccurrence)
class TaskOccurrenceAdmin(admin.ModelAdmin):
    list_display = ("template", "assigned_to", "deadline", "status", "snooze_count", "points_earned", "reassignment_reason")
    list_filter = ("status", "reassignment_reason", "deadline", "template__group")
    search_fields = ("template__name", "assigned_to__email")
    autocomplete_fields = ("template", "assigned_to", "original_assignee")


@admin.register(models.TaskPreference)
class TaskPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "task_template", "preference", "last_updated")
    list_filter = ("preference", "task_template__group")
    search_fields = ("user__email", "task_template__name")
    autocomplete_fields = ("user", "task_template")


@admin.register(models.TaskSwap)
class TaskSwapAdmin(admin.ModelAdmin):
    list_display = ("task", "from_user", "to_user", "status", "swap_type", "counterpart_task", "created_at", "decided_at")
    list_filter = ("status", "swap_type", "task__template__group")
    search_fields = ("task__template__name", "from_user__email", "to_user__email")
    autocomplete_fields = ("task", "from_user", "to_user", "counterpart_task")


@admin.register(models.TaskProposal)
class TaskProposalAdmin(admin.ModelAdmin):
    list_display = ("proposal_name", "group", "proposed_by", "state", "approved_by", "created_at")
    list_filter = ("state", "group")
    search_fields = ("proposed_payload", "group__name", "proposed_by__email")
    autocomplete_fields = ("proposed_by", "group", "task_template", "approved_by")
    readonly_fields = ("proposed_payload", "payload_diff_display", "created_at", "updated_at")

    @admin.display(description="Task Name")
    def proposal_name(self, obj):
        return obj.proposed_payload.get("name", f"Proposal #{obj.pk}") if obj.proposed_payload else f"Proposal #{obj.pk}"

    @admin.display(description="Moderator Edits")
    def payload_diff_display(self, obj):
        diff = obj.payload_diff
        if not diff:
            return "No changes"
        return "; ".join(f"{k}: {v['from']} → {v['to']}" for k, v in diff.items())


# -------------------------------------------------------------------
# Calendar, Events, External Credentials, Group Calendar
# -------------------------------------------------------------------

@admin.register(models.ExternalCredential)
class ExternalCredentialAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "account_email", "expires_at", "last_refreshed_at")
    list_filter = ("provider",)
    search_fields = ("user__email", "account_email")
    autocomplete_fields = ("user",)


class EventInline(admin.TabularInline):
    model = models.Event
    extra = 0


@admin.register(models.Calendar)
class CalendarAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "provider",
        "name",
        "external_id",
        "push_enabled",
        "is_task_writeback",
        "include_in_availability",
    )
    list_filter = ("provider", "push_enabled", "is_task_writeback", "include_in_availability")
    search_fields = ("name", "external_id", "user__email")
    autocomplete_fields = ("user", "credential")
    inlines = [EventInline]


@admin.register(models.GoogleCalendarSync)
class GoogleCalendarSyncAdmin(admin.ModelAdmin):
    list_display = ("calendar", "channel_id", "watch_expires_at", "paused", "active_task_id", "oauth_writable")
    list_filter = ("paused", "oauth_writable")
    search_fields = ("calendar__name", "calendar__user__email", "channel_id")
    autocomplete_fields = ("calendar",)


@admin.register(models.OutlookCalendarSync)
class OutlookCalendarSyncAdmin(admin.ModelAdmin):
    list_display = ("calendar", "subscription_id", "subscription_expires_at")
    search_fields = ("calendar__name", "calendar__user__email")
    autocomplete_fields = ("calendar",)


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "calendar",
        "source",
        "start",
        "end",
        "blocks_availability",
        "status",
        "external_event_id",
        "external_calendar_id",
        "external_updated",
    )
    list_filter = ("source", "blocks_availability", "status", "calendar__provider")
    search_fields = ("title", "calendar__name", "external_event_id")
    autocomplete_fields = ("calendar", "task_occurrence")



# -------------------------------------------------------------------
# Messaging and Notifications
# -------------------------------------------------------------------

class MessageReceiptInline(admin.TabularInline):
    model = models.MessageReceipt
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(models.Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("group", "sender", "short_content", "timestamp")
    list_filter = ("group",)
    search_fields = ("content", "sender__email", "group__name")
    autocomplete_fields = ("group", "sender")
    inlines = [MessageReceiptInline]

    def short_content(self, obj):
        return (obj.content[:50] + "…") if len(obj.content) > 50 else obj.content
    short_content.short_description = "Content"


@admin.register(models.MessageReceipt)
class MessageReceiptAdmin(admin.ModelAdmin):
    list_display = ("message", "user", "seen_at")
    list_filter = ("seen_at",)
    search_fields = ("message__content", "user__email")
    autocomplete_fields = ("message", "user")


@admin.register(models.Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "title", "type", "read", "dismissed", "created_at")
    list_filter = ("type", "read", "dismissed")
    search_fields = ("recipient__email", "title", "content")
    autocomplete_fields = ("recipient", "group", "task_occurrence", "task_proposal", "message")


# -------------------------------------------------------------------
# Stats, Badges
# -------------------------------------------------------------------

@admin.register(models.UserStats)
class UserStatsAdmin(admin.ModelAdmin):
    list_display = ("user", "household", "current_streak_days", "longest_streak_days", "total_tasks_completed", "total_points", "on_time_completion_rate", "last_updated")
    list_filter = ("household",)
    search_fields = ("user__email", "household__name")
    autocomplete_fields = ("user", "household")


@admin.register(models.Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("name", "points_value", "description")
    search_fields = ("name", "description")
    readonly_fields = ("criteria",)


@admin.register(models.UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "badge", "household", "awarded_at")
    list_filter = ("badge", "household")
    search_fields = ("user__email", "badge__name", "household__name")
    autocomplete_fields = ("user", "badge", "household")


# -------------------------------------------------------------------
# AI Assistant
# -------------------------------------------------------------------
@admin.register(models.ChatbotSession)
class ChatbotSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "message_count", "last_active", "created_at")
    list_filter = ("created_at", "last_active")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "messages_pretty", "pending_action", "created_at", "last_active")
    ordering = ("-last_active",)

    def message_count(self, obj):
        return len(obj.messages or [])
    message_count.short_description = "Messages"

    def messages_pretty(self, obj):
        from django.utils.html import format_html, escape
        lines = []
        for m in (obj.messages or []):
            role = m.get("role", "?")
            content = escape(m.get("content", ""))
            colour = "#0066cc" if role == "user" else "#2a7a2a"
            lines.append(
                f'<p><strong style="color:{colour}">[{role}]</strong> {content}</p>'
            )
        return format_html("".join(lines) or "<em>No messages</em>")
    messages_pretty.short_description = "Conversation"

    def has_add_permission(self, request):
        return False

