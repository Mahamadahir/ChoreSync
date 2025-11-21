from django.contrib import admin
from . import models
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _


# -------------------------------------------------------------------
# Group & Membership
# -------------------------------------------------------------------
@admin.register(models.User)
class UserAdmin(DjangoUserAdmin):
    """Admin config for the custom User model."""

    list_display = ("username", "email", "is_staff", "is_active")
    search_fields = ("username", "email")
    ordering = ("username",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
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
    list_display = ("name", "group", "recurring_choice", "recur_value", "next_due", "active")
    list_filter = ("active", "recurring_choice", "group")
    search_fields = ("name", "group__name")
    autocomplete_fields = ("creator", "group")
    inlines = [TaskOccurrenceInline]


@admin.register(models.TaskOccurrence)
class TaskOccurrenceAdmin(admin.ModelAdmin):
    list_display = ("template", "assigned_to", "deadline", "completed")
    list_filter = ("completed", "deadline", "template__group")
    search_fields = ("template__name", "assigned_to__email")
    autocomplete_fields = ("template", "assigned_to")


@admin.register(models.TaskPreference)
class TaskPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "task_template", "preference", "last_updated")
    list_filter = ("preference", "task_template__group")
    search_fields = ("user__email", "task_template__name")
    autocomplete_fields = ("user", "task_template")


@admin.register(models.TaskSwap)
class TaskSwapAdmin(admin.ModelAdmin):
    list_display = ("task", "from_user", "to_user", "status", "created_at", "decided_at")
    list_filter = ("status", "task__template__group")
    search_fields = ("task__template__name", "from_user__email", "to_user__email")
    autocomplete_fields = ("task", "from_user", "to_user")


class TaskVoteInline(admin.TabularInline):
    model = models.TaskVote
    extra = 0
    autocomplete_fields = ("voter",)


@admin.register(models.TaskProposal)
class TaskProposalAdmin(admin.ModelAdmin):
    list_display = ("task_template", "group", "proposed_by", "state", "required_support_ratio", "created_at")
    list_filter = ("state", "group")
    search_fields = ("task_template__name", "group__name", "proposed_by__email")
    autocomplete_fields = ("proposed_by", "group", "task_template")
    inlines = [TaskVoteInline]


@admin.register(models.TaskVote)
class TaskVoteAdmin(admin.ModelAdmin):
    list_display = ("proposal", "voter", "choice", "created_at")
    list_filter = ("choice",)
    search_fields = ("proposal__task_template__name", "voter__email")
    autocomplete_fields = ("proposal", "voter")


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
    list_display = ("user", "provider", "name", "external_id", "sync_enabled", "back_sync_enabled", "include_in_availability")
    list_filter = ("provider", "sync_enabled", "back_sync_enabled", "include_in_availability")
    search_fields = ("name", "external_id", "user__email")
    autocomplete_fields = ("user", "credential")
    inlines = [EventInline]


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "calendar", "source", "start", "end", "blocks_availability", "status")
    list_filter = ("source", "blocks_availability", "status", "calendar__provider")
    search_fields = ("title", "calendar__name")
    autocomplete_fields = ("calendar", "task_occurrence")


@admin.register(models.GroupCalendar)
class GroupCalendarAdmin(admin.ModelAdmin):
    list_display = ("group", "timezone", "show_member_calendars", "show_group_tasks")
    list_filter = ("show_member_calendars", "show_group_tasks")
    search_fields = ("group__name",)
    autocomplete_fields = ("group",)


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
    list_display = ("recipient", "type", "group", "task_occurrence", "task_proposal", "message", "read", "dismissed", "created_at")
    list_filter = ("type", "read", "dismissed")
    search_fields = ("recipient__email", "content")
    autocomplete_fields = ("recipient", "group", "task_occurrence", "task_proposal", "message")

