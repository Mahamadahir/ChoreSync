"""
Chatbot router — conversational task assistant powered by Gemini.

Uses native function calling for intent detection and parameter extraction.
The model drives clarification (including chip generation) via ask_clarification().
No manual state machine — conversation history carries context between turns.
"""
from __future__ import annotations

import httpx
import logging
from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError

logger = logging.getLogger("chore_sync")

from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from chore_sync.api.views import CsrfExemptSessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from chore_sync.models import (
    ChatbotSession, Group, GroupMembership, MarketplaceListing,
    TaskAssignmentHistory, TaskOccurrence, TaskSwap,
    TaskTemplate, UserStats, UserBadge,
)
from chore_sync.services.task_lifecycle_service import TaskLifecycleService
from chore_sync.services.task_template_service import TaskTemplateService
from chore_sync.services.task_preference_service import TaskPreferenceService
from chore_sync.services.marketplace_service import MarketplaceService
from chore_sync.services.group_service import GroupOrchestrator
from chore_sync.services.proposal_service import ProposalService

GEMINI_API_KEY        = getattr(settings, 'GEMINI_API_KEY', '')
GEMINI_PRIMARY_MODEL  = getattr(settings, 'GEMINI_MODEL',          'gemma-4-31b-it')
GEMINI_FALLBACK_MODEL = getattr(settings, 'GEMINI_FALLBACK_MODEL',  'gemma-3-27b-it')
GEMINI_BASE_URL       = 'https://generativelanguage.googleapis.com/v1beta/models/'

DAY_INT_TO_ABBR = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}
DAY_NAME_TO_INT = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
    'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6,
}

# ──────────────────────────────────────────────────────────────────────────────
# Function declarations — the model picks and fills these instead of JSON intents
# ──────────────────────────────────────────────────────────────────────────────

FUNCTION_DECLARATIONS = [
    {
        "name": "ask_clarification",
        "description": (
            "Ask the user for a missing piece of information before proceeding. "
            "Use this whenever a required parameter is unknown or ambiguous."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Clear, concise question for the user."},
                "chips": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3–6 short option labels the user can tap as a quick reply.",
                },
            },
            "required": ["question", "chips"],
        },
    },
    {
        "name": "create_task",
        "description": (
            "Create a new recurring or one-off task template in a group. "
            "Requires moderator role — if the user lacks permission, use propose_task instead. "
            "Before calling, always collect via ask_clarification: "
            "(1) name, (2) recurrence, (3) day_of_week if weekly, (4) day_of_month if monthly, "
            "(5) time_of_day — always ask even if not mentioned, "
            "(6) estimated_minutes — always ask even if not mentioned. "
            "When asking for day_of_week always offer all 7 days as chips. "
            "Only call this function once all six fields are known."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name":              {"type": "string"},
                "recurrence":        {"type": "string", "enum": ["daily", "weekly", "fortnightly", "monthly", "once"]},
                "day_of_week":       {"type": "string", "enum": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"], "description": "Required for weekly."},
                "day_of_month":      {"type": "integer", "description": "Day 1–28, required for monthly."},
                "time_of_day":       {"type": "string", "description": "24 h HH:MM format. Must be collected before calling."},
                "estimated_minutes": {"type": "integer", "description": "How long the task takes in minutes. Must be collected before calling."},
                "difficulty":        {"type": "integer", "description": "1 (easy) – 5 (hard)."},
                "category":          {"type": "string", "enum": ["cleaning", "cooking", "laundry", "maintenance", "other"]},
                "group_name":        {"type": "string"},
                "assign_to_name":    {"type": "string"},
            },
            "required": ["name", "recurrence", "time_of_day", "estimated_minutes"],
        },
    },
    {
        "name": "propose_task",
        "description": (
            "Submit a task suggestion for moderator approval or group vote. "
            "Use when the user is not a moderator, or when they explicitly want to suggest rather than create."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_name":         {"type": "string"},
                "recurrence":        {"type": "string", "enum": ["daily", "weekly", "fortnightly", "monthly", "once"]},
                "day_of_week":       {"type": "string", "enum": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]},
                "day_of_month":      {"type": "integer"},
                "time_of_day":       {"type": "string"},
                "estimated_minutes": {"type": "integer"},
                "category":          {"type": "string", "enum": ["cleaning", "cooking", "laundry", "maintenance", "other"]},
                "reason":            {"type": "string"},
                "group_name":        {"type": "string"},
                "vote_mode":         {"type": "boolean", "description": "True = group vote, False = moderator review."},
            },
            "required": ["task_name"],
        },
    },
    {
        "name": "complete_task",
        "description": "Mark one of the user's pending tasks as completed.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_name": {"type": "string", "description": "Full or partial task name."},
            },
        },
    },
    {
        "name": "snooze_task",
        "description": "Snooze a specific pending task for a number of hours.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_name":    {"type": "string"},
                "snooze_hours": {"type": "integer", "description": "Hours to snooze. Default 3."},
            },
        },
    },
    {
        "name": "snooze_all_tasks",
        "description": "Snooze all of the user's pending tasks.",
        "parameters": {
            "type": "object",
            "properties": {
                "snooze_hours": {"type": "integer", "description": "Hours to snooze. Default 3."},
            },
        },
    },
    {
        "name": "query_my_tasks",
        "description": "List the user's pending and upcoming tasks.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "query_group_tasks",
        "description": "List all active tasks in a group.",
        "parameters": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"},
            },
        },
    },
    {
        "name": "query_stats",
        "description": "Show the user's personal stats: points, streak, completion rate.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "query_badges",
        "description": "Show the user's earned badges.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "query_leaderboard",
        "description": "Show the points leaderboard for a group.",
        "parameters": {
            "type": "object",
            "properties": {
                "group_name": {"type": "string"},
            },
        },
    },
    {
        "name": "query_swap_requests",
        "description": "List pending swap requests sent to the user.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "set_preference",
        "description": "Set the user's preference for a task template.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_name":  {"type": "string"},
                "preference": {"type": "string", "enum": ["prefer", "neutral", "avoid"]},
            },
            "required": ["task_name", "preference"],
        },
    },
    {
        "name": "claim_marketplace_task",
        "description": "Claim a task currently listed on the group marketplace.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_name":  {"type": "string"},
                "group_name": {"type": "string"},
            },
        },
    },
    {
        "name": "accept_swap",
        "description": "Accept a pending swap request from another member.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_name": {"type": "string"},
            },
        },
    },
    {
        "name": "accept_emergency_task",
        "description": "Volunteer to take over an emergency task that has been broadcast to the group.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_name": {"type": "string"},
            },
        },
    },
    {
        "name": "emergency_reassign_task",
        "description": "Broadcast one of the user's tasks as an emergency so group members can volunteer.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_name": {"type": "string"},
                "reason":    {"type": "string"},
            },
        },
    },
    {
        "name": "list_task_on_marketplace",
        "description": "Put one of the user's tasks on the marketplace so anyone in the group can claim it.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_name":    {"type": "string"},
                "bonus_points": {"type": "integer", "description": "Optional bonus points offered to claimer."},
            },
        },
    },
    {
        "name": "request_task_swap",
        "description": "Request a task swap with a specific group member.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_name":      {"type": "string"},
                "swap_with_name": {"type": "string"},
                "reason":         {"type": "string"},
            },
        },
    },
    {
        "name": "create_group",
        "description": "Create a new household group.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "join_group",
        "description": "Join an existing group using its join code.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "invite_member",
        "description": "Invite someone to a group by email address. Moderator only.",
        "parameters": {
            "type": "object",
            "properties": {
                "email":      {"type": "string"},
                "group_name": {"type": "string"},
            },
            "required": ["email"],
        },
    },
    {
        "name": "delete_task_template",
        "description": (
            "Permanently delete a task template and cancel all pending occurrences. Moderator only. "
            "IMPORTANT: always call ask_clarification to confirm before calling this function."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_name":  {"type": "string"},
                "group_name": {"type": "string"},
            },
            "required": ["task_name"],
        },
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# System prompt — describes behaviour, not JSON shapes
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a task assistant for ChoreSync, a household chore app.
Use the available functions to help users manage their tasks and groups.

Rules:
- Ask ONE question at a time. Never combine multiple questions into one message.
- Every ask_clarification call MUST include chips. Never call ask_clarification without a chips array.
- For create_task, collect fields in this order, one per turn: (1) recurrence, (2) day_of_week if weekly — always offer all 7 days as chips, (3) day_of_month if monthly, (4) time_of_day — offer time chips like ["8:00 AM","12:00 PM","3:00 PM","6:00 PM","8:00 PM","You choose"], (5) estimated_minutes — offer chips like ["15 min","30 min","45 min","1 hour","1.5 hours","You choose"]. Only call create_task once all fields are collected.
- When the user says "you choose", "doesn't matter", or similar — pick a sensible default based on the task name and context. Do NOT ask again.
- create_task requires moderator role. If the response indicates the user lacks permission, switch to propose_task.
- For "I can't do X" without a specified action, use ask_clarification to find out what they want: emergency reassign, marketplace, or swap.
- Always call ask_clarification to confirm before calling delete_task_template.
- Match tasks by partial name — users rarely type exact task names."""


# ──────────────────────────────────────────────────────────────────────────────
# Gemini API
# ──────────────────────────────────────────────────────────────────────────────

def _call_gemini(messages: list[dict]) -> dict | None:
    """Call Gemini with function calling enabled.

    Returns one of:
      {"type": "function_call", "name": str, "args": dict}
      {"type": "text", "content": str}
      None  — all models failed
    """
    system_text = None
    turns = []
    for msg in messages:
        role, content = msg["role"], msg["content"]
        if role == "system":
            system_text = content
        elif role == "assistant":
            turns.append({"role": "model", "parts": [{"text": content}]})
        else:
            turns.append({"role": "user", "parts": [{"text": content}]})

    payload: dict = {
        "contents": turns,
        "tools": [{"function_declarations": FUNCTION_DECLARATIONS}],
        "tool_config": {"function_calling_config": {"mode": "AUTO"}},
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
    }
    if system_text:
        payload["system_instruction"] = {"parts": [{"text": system_text}]}

    for model in (GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL):
        url = f"{GEMINI_BASE_URL}{model}:generateContent"
        logger.debug("Chatbot → Gemini | model=%s | turns=%d", model, len(turns))
        try:
            resp = httpx.post(
                url,
                json=payload,
                headers={"X-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                timeout=60,
            )
        except httpx.RequestError as exc:
            logger.warning("Chatbot request error (model=%s): %s — trying next", model, exc)
            continue
        if not resp.is_success:
            logger.warning("Chatbot HTTP %s (model=%s): %s — trying next", resp.status_code, model, resp.text[:200])
            continue
        body = resp.json()
        try:
            parts = body["candidates"][0]["content"]["parts"]
            part  = next(p for p in parts if not p.get("thought"))
            if "functionCall" in part:
                fc = part["functionCall"]
                logger.debug("Chatbot ← fn=%s args=%s", fc["name"], str(fc.get("args", {}))[:200])
                return {"type": "function_call", "name": fc["name"], "args": fc.get("args", {})}
            text = part.get("text", "").strip()
            logger.debug("Chatbot ← text: %s", text[:200])
            return {"type": "text", "content": text}
        except (KeyError, IndexError, StopIteration):
            logger.warning("Chatbot unexpected response shape (model=%s): %s — trying next", model, str(body)[:200])
            continue

    logger.error("Chatbot: all models failed")
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────────────

def _name(user) -> str:
    return user.first_name or user.username


def _find_user_occurrence(user, task_name: str | None) -> TaskOccurrence | None:
    qs = TaskOccurrence.objects.filter(
        assigned_to=user, status__in=['pending', 'snoozed']
    ).select_related('template')
    if not task_name:
        return qs.order_by('deadline').first()
    low = task_name.lower()
    for occ in qs.order_by('deadline'):
        if low in occ.template.name.lower():
            return occ
    return None


def _find_member_by_name(user, name: str):
    low = name.lower()
    memberships = GroupMembership.objects.filter(
        group__in=GroupMembership.objects.filter(user=user).values('group')
    ).exclude(user=user).select_related('user')
    for m in memberships:
        u = m.user
        if (low in u.first_name.lower() or low in u.last_name.lower() or
                low in u.username.lower() or
                low in f"{u.first_name} {u.last_name}".lower()):
            return u
    return None


def _find_group(user, group_name: str | None) -> Group | None:
    groups = _find_groups(user, group_name)
    return groups[0] if groups else None


def _find_groups(user, group_name: str | None) -> list[Group]:
    qs = GroupMembership.objects.filter(user=user, group__is_personal=False).select_related('group').order_by('group__name')
    if not group_name:
        return [m.group for m in qs]
    low = group_name.lower()
    return [m.group for m in qs if low in m.group.name.lower()]


def _find_template(user, task_name: str, group: Group | None = None) -> TaskTemplate | None:
    qs = TaskTemplate.objects.filter(
        group__in=GroupMembership.objects.filter(user=user).values('group'),
        active=True,
    )
    if group:
        qs = qs.filter(group=group)
    low = task_name.lower()
    for t in qs:
        if low in t.name.lower():
            return t
    return None


def _emergency_reassigns_used(user) -> int:
    now = timezone.now()
    return TaskAssignmentHistory.objects.filter(
        user=user, was_emergency=True,
        assigned_at__year=now.year, assigned_at__month=now.month,
    ).count()


def _parse_day_field(raw) -> int | None:
    if isinstance(raw, str):
        return DAY_NAME_TO_INT.get(raw.lower().strip())
    if isinstance(raw, int) and 0 <= raw <= 6:
        return raw
    return None


def _parse_time_str(raw: str | None) -> tuple[int, int]:
    if not raw:
        return 20, 0
    try:
        h, m = raw.strip().split(':')
        return int(h), int(m)
    except (ValueError, AttributeError):
        return 20, 0


def _compute_next_due(recurrence, day_of_week, time_of_day=None, day_of_month=None, user_tz_str=None):
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        user_tz = ZoneInfo(user_tz_str) if user_tz_str else ZoneInfo('UTC')
    except (ZoneInfoNotFoundError, Exception):
        user_tz = ZoneInfo('UTC')
    utc = ZoneInfo('UTC')
    now_utc = timezone.now()
    now     = now_utc.astimezone(user_tz)
    hour, minute = _parse_time_str(time_of_day)

    if recurrence == 'monthly' and day_of_month:
        dom  = max(1, min(28, day_of_month))
        base = now.replace(day=dom, hour=hour, minute=minute, second=0, microsecond=0)
        if base <= now:
            base = base.replace(month=base.month + 1) if base.month < 12 else base.replace(year=base.year + 1, month=1)
        return base.astimezone(utc)

    if day_of_week is None or recurrence in ('once', 'daily', 'fortnightly'):
        base = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if base <= now:
            base += timedelta(days=1)
        return base.astimezone(utc)

    days_ahead = (day_of_week - now.weekday()) % 7
    base = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if days_ahead == 0 and base <= now:
        base += timedelta(days=7)
    return base.astimezone(utc)


def _build_payload(args: dict, user_tz_str: str | None = None) -> tuple[dict, int | None]:
    recurrence   = (args.get('recurrence') or 'weekly').lower()
    day_of_week  = _parse_day_field(args.get('day_of_week'))
    day_of_month = args.get('day_of_month')
    time_of_day  = args.get('time_of_day')

    if recurrence == 'once':
        recurring_choice, days_of_week_list, recur_value = 'none', None, None
    elif recurrence == 'daily':
        recurring_choice, days_of_week_list, recur_value = 'every_n_days', None, 1
    elif recurrence == 'fortnightly':
        recurring_choice, days_of_week_list, recur_value = 'every_n_days', None, 14
    elif recurrence == 'monthly':
        recurring_choice, days_of_week_list, recur_value = 'monthly', None, None
    elif day_of_week is not None:
        recurring_choice, days_of_week_list, recur_value = 'custom', [DAY_INT_TO_ABBR[day_of_week]], None
    else:
        recurring_choice, days_of_week_list, recur_value = 'weekly', None, None

    next_due = _compute_next_due(recurrence, day_of_week, time_of_day, day_of_month, user_tz_str)

    payload = {
        "name":             args.get("name", "New Task"),
        "recurring_choice": recurring_choice,
        "days_of_week":     days_of_week_list,
        "estimated_mins":   args.get("estimated_minutes") or 30,
        "difficulty":       args.get("difficulty") or 2,
        "category":         args.get("category") or "other",
        "next_due":         next_due,
    }
    if recur_value:
        payload["recur_value"] = recur_value
    return payload, recur_value


def _freq_label(recurring_choice, recur_value, day_of_week, day_of_month) -> str:
    day_names = ['Mondays', 'Tuesdays', 'Wednesdays', 'Thursdays', 'Fridays', 'Saturdays', 'Sundays']
    if recurring_choice == 'none':
        return 'one-off'
    if recurring_choice == 'every_n_days':
        return 'every day' if recur_value == 1 else f'every {recur_value} days'
    if recurring_choice == 'custom':
        return f'every {day_names[day_of_week]}' if day_of_week is not None else 'custom'
    if recurring_choice == 'monthly':
        if day_of_month:
            suffix = 'st' if day_of_month == 1 else ('nd' if day_of_month == 2 else ('rd' if day_of_month == 3 else 'th'))
            return f'monthly on the {day_of_month}{suffix}'
        return 'monthly'
    return recurring_choice


def _build_and_create(user, args: dict, group) -> str:
    user_tz = getattr(user, 'timezone', None) or 'UTC'
    payload, recur_value = _build_payload(args, user_tz_str=user_tz)
    try:
        template = TaskTemplateService().create_template(
            creator=user, group_id=str(group.id), payload=payload,
        )
    except DjangoValidationError as exc:
        msgs = '; '.join(
            f"{f}: {', '.join(errs)}" for f, errs in exc.message_dict.items()
        ) if hasattr(exc, 'message_dict') else str(exc)
        return f"Couldn't create task — invalid details: {msgs}"
    except ValueError as exc:
        return f"Couldn't create task: {exc}"

    TaskLifecycleService().generate_recurring_instances(task_template_id=str(template.id))

    day_of_week  = _parse_day_field(args.get('day_of_week'))
    day_of_month = args.get('day_of_month')
    time_of_day  = args.get('time_of_day')
    freq_str  = _freq_label(payload['recurring_choice'], recur_value, day_of_week, day_of_month)
    time_str  = f' at {time_of_day}' if time_of_day else ''
    return f"Done! Created **{template.name}** ({freq_str}{time_str}) in **{group.name}**."


# ──────────────────────────────────────────────────────────────────────────────
# Function handlers  (user, args: dict) -> str
# ──────────────────────────────────────────────────────────────────────────────

def _handle_create_task(user, args: dict) -> str:
    candidates = _find_groups(user, args.get("group_name"))
    if not candidates:
        hint = args.get("group_name")
        return f"I couldn't find a group called **{hint}**." if hint else "You're not in any group yet."
    if len(candidates) > 1:
        names = ", ".join(f"**{g.name}**" for g in candidates)
        return f"You're in multiple groups ({names}). Which one should I add this task to?"
    group = candidates[0]

    membership = GroupMembership.objects.filter(user=user, group=group).first()
    if not membership or membership.role != 'moderator':
        name = args.get('name', 'this task')
        return (
            f"You don't have permission to create tasks directly in **{group.name}**. "
            f"Would you like to submit **{name}** as a suggestion instead? "
            f"Try saying 'propose {name} for {group.name}'."
        )

    return _build_and_create(user, args, group)


def _handle_propose_task(user, args: dict) -> str:
    task_name = args.get("task_name", "").strip()
    if not task_name:
        return "What task would you like to suggest?"
    group = _find_group(user, args.get("group_name"))
    if not group:
        return "I couldn't find that group."

    normalized = {**args, "name": task_name}
    user_tz = getattr(user, 'timezone', None) or 'UTC'
    proposal_payload, _ = _build_payload(normalized, user_tz_str=user_tz)
    vote_mode = bool(args.get("vote_mode", False))
    try:
        ProposalService().create_proposal(
            proposer_id=str(user.id),
            group_id=str(group.id),
            payload=proposal_payload,
            reason=args.get("reason") or "",
            vote_mode=vote_mode,
        )
    except ValueError as exc:
        return f"Couldn't submit suggestion: {exc}"

    if vote_mode:
        return (
            f"**{task_name}** has been put to a group vote in **{group.name}**. "
            f"Members will be notified to cast their votes."
        )
    return (
        f"Suggestion submitted for **{task_name}** in **{group.name}**. "
        f"A moderator will be notified to review it."
    )


def _handle_complete_task(user, args: dict) -> str:
    occ = _find_user_occurrence(user, args.get("task_name"))
    if not occ:
        return "I couldn't find that task in your pending tasks."
    try:
        TaskLifecycleService().toggle_occurrence_completed(
            occurrence_id=str(occ.id), actor_id=str(user.id)
        )
        return f"Marked **{occ.template.name}** as complete!"
    except Exception as exc:
        return f"Couldn't complete that task: {exc}"


def _handle_snooze_task(user, args: dict) -> str:
    occ = _find_user_occurrence(user, args.get("task_name"))
    if not occ:
        return "I couldn't find that task in your pending tasks."
    hours       = int(args.get("snooze_hours") or 3)
    snooze_until = timezone.now() + timedelta(hours=hours)
    try:
        TaskLifecycleService().snooze_task(
            occurrence_id=str(occ.id), snooze_until=snooze_until, actor_id=str(user.id)
        )
        return f"Snoozed **{occ.template.name}** for {hours}h (until {snooze_until.strftime('%H:%M')})."
    except Exception as exc:
        return f"Couldn't snooze: {exc}"


def _handle_snooze_all(user, args: dict) -> str:
    hours        = int(args.get("snooze_hours") or 3)
    snooze_until = timezone.now() + timedelta(hours=hours)
    svc  = TaskLifecycleService()
    occs = list(TaskOccurrence.objects.filter(
        assigned_to=user, status='pending'
    ).select_related('template'))
    if not occs:
        return "You have no pending tasks to snooze."
    succeeded, failed = 0, []
    for occ in occs:
        try:
            svc.snooze_task(occurrence_id=str(occ.id), snooze_until=snooze_until, actor_id=str(user.id))
            succeeded += 1
        except Exception as exc:
            failed.append(occ.template.name)
            logger.warning("snooze_all failed for occ %s: %s", occ.id, exc)
    if succeeded == 0:
        return "Couldn't snooze any tasks right now. Please try again."
    msg = f"Snoozed {succeeded} task(s) for {hours}h (until {snooze_until.strftime('%H:%M')})."
    if failed:
        msg += f" ⚠️ Could not snooze: {', '.join(failed)}."
    return msg


def _handle_query_tasks(user, _args: dict) -> str:
    buckets = TaskLifecycleService().list_user_tasks(user_id=str(user.id))
    occs = sorted(buckets['active'] + buckets['upcoming'], key=lambda o: o.deadline)[:10]
    if not occs:
        return "You have no pending tasks right now."
    lines = [f"Your pending tasks ({len(occs)}):"]
    for occ in occs:
        suffix = " *(snoozed)*" if occ.status == 'snoozed' else ""
        lines.append(f"• **{occ.template.name}** — due {occ.deadline.strftime('%a %d %b, %H:%M')}{suffix}")
    return "\n".join(lines)


def _handle_query_group_tasks(user, args: dict) -> str:
    group = _find_group(user, args.get("group_name"))
    if not group:
        return "I couldn't find that group."
    try:
        all_occs = TaskLifecycleService().list_group_tasks(group_id=str(group.id), actor_id=str(user.id))
    except PermissionError:
        return "I couldn't find that group."
    occs = [o for o in all_occs if o.status in ('pending', 'snoozed', 'overdue')][:15]
    if not occs:
        return f"No pending tasks in **{group.name}**."
    lines = [f"Tasks in **{group.name}**:"]
    for occ in occs:
        assignee = _name(occ.assigned_to) if occ.assigned_to else "Unassigned"
        lines.append(f"• **{occ.template.name}** — {assignee}, due {occ.deadline.strftime('%a %d %b')}")
    return "\n".join(lines)


def _handle_query_stats(user, _args: dict) -> str:
    memberships = GroupMembership.objects.filter(user=user, group__is_personal=False).select_related('group')
    if not memberships:
        return "You're not in any group yet."
    lines = [f"Stats for **{_name(user)}**:"]
    for m in memberships:
        s = UserStats.objects.filter(user=user, group=m.group).first()
        if s:
            lines.append(
                f"\n**{m.group.name}:** {s.total_tasks_completed} tasks · "
                f"{s.total_points} pts · {s.current_streak_days}-day streak · "
                f"{round(s.on_time_completion_rate * 100)}% on time"
            )
    return "\n".join(lines)


def _handle_query_badges(user, _args: dict) -> str:
    badges = UserBadge.objects.filter(user=user).select_related('badge').order_by('-awarded_at')[:10]
    if not badges:
        return "You haven't earned any badges yet. Complete tasks to start earning!"
    lines = [f"Your badges ({badges.count()}):"]
    for ub in badges:
        lines.append(f"• **{ub.badge.name}** — {ub.badge.description}")
    return "\n".join(lines)


def _handle_query_leaderboard(user, args: dict) -> str:
    group = _find_group(user, args.get("group_name"))
    if not group:
        return "I couldn't find that group."
    stats = UserStats.objects.filter(group=group).select_related('user').order_by('-total_points')[:8]
    if not stats:
        return f"No leaderboard data yet for **{group.name}**."
    lines = [f"Leaderboard — **{group.name}**:"]
    for i, s in enumerate(stats, 1):
        marker = " ← you" if s.user_id == user.id else ""
        lines.append(
            f"{i}. {_name(s.user)} — {s.total_points} pts · "
            f"{s.current_streak_days}-day streak{marker}"
        )
    return "\n".join(lines)


def _handle_query_swap_requests(user, _args: dict) -> str:
    swaps = TaskSwap.objects.filter(
        to_user=user, status='pending'
    ).select_related('task__template', 'from_user').order_by('expires_at')
    if not swaps:
        return "You have no pending swap requests."
    lines = [f"Pending swap requests ({swaps.count()}):"]
    for sw in swaps:
        expires = sw.expires_at.strftime('%a %d %b') if sw.expires_at else "soon"
        lines.append(
            f"• **{sw.task.template.name}** from {_name(sw.from_user)} "
            f"— expires {expires}"
        )
    lines.append("\nSay 'accept [task name] swap' to accept one.")
    return "\n".join(lines)


def _handle_set_preference(user, args: dict) -> str:
    task_name  = args.get("task_name", "")
    preference = args.get("preference", "neutral")
    template   = _find_template(user, task_name)
    if not template:
        return f"I couldn't find a task called '{task_name}' in your groups."
    try:
        TaskPreferenceService().set_preference(user=user, template=template, preference=preference)
    except (ValueError, PermissionError) as exc:
        return f"Couldn't save preference: {exc}"
    verb = {"prefer": "You'll be prioritised for", "avoid": "You'll be deprioritised for", "neutral": "You're neutral on"}[preference]
    return f"{verb} **{template.name}**. Preference saved."


def _handle_claim_marketplace(user, args: dict) -> str:
    group = _find_group(user, args.get("group_name"))
    if not group:
        return "I couldn't find that group."
    listings = MarketplaceListing.objects.filter(
        task_occurrence__template__group=group,
        expires_at__gt=timezone.now(),
    ).select_related('task_occurrence__template', 'listed_by')
    if not listings:
        return f"There's nothing on the marketplace in **{group.name}** right now."

    task_name = args.get("task_name")
    if not task_name:
        lines = [f"Marketplace listings in **{group.name}**:"]
        for lst in listings[:8]:
            bonus = f" (+{lst.bonus_points} pts)" if lst.bonus_points else ""
            lines.append(f"• **{lst.task_occurrence.template.name}**{bonus} — listed by {_name(lst.listed_by)}")
        lines.append("\nSay 'claim [task name]' to take one.")
        return "\n".join(lines)

    low   = task_name.lower()
    match = next((l for l in listings if low in l.task_occurrence.template.name.lower()), None)
    if not match:
        return f"I couldn't find '{task_name}' on the marketplace."
    try:
        MarketplaceService().claim_task(user=user, listing_id=match.id)
        bonus_str = f" You earned +{match.bonus_points} bonus points!" if match.bonus_points else ""
        return f"Claimed **{match.task_occurrence.template.name}**!{bonus_str}"
    except Exception as exc:
        return f"Couldn't claim that task: {exc}"


def _handle_accept_swap(user, args: dict) -> str:
    task_name = args.get("task_name")
    qs   = TaskSwap.objects.filter(to_user=user, status='pending').select_related('task__template')
    swap = next((s for s in qs if task_name and task_name.lower() in s.task.template.name.lower()), None) \
           or qs.order_by('expires_at').first()
    if not swap:
        return "I couldn't find a pending swap request for that task."
    try:
        TaskLifecycleService().respond_to_swap_request(
            swap_id=str(swap.id), accept=True, actor_id=str(user.id)
        )
        return f"Accepted the swap for **{swap.task.template.name}**. It's now yours."
    except Exception as exc:
        return f"Couldn't accept swap: {exc}"


def _handle_accept_emergency(user, args: dict) -> str:
    task_name = args.get("task_name")
    qs = TaskOccurrence.objects.filter(
        status='pending',
        reassignment_reason='emergency',
        assigned_to__isnull=True,
        template__group__in=GroupMembership.objects.filter(user=user).values('group'),
    ).select_related('template')
    occ = next((o for o in qs if task_name and task_name.lower() in o.template.name.lower()), None) \
          or qs.order_by('deadline').first()
    if not occ:
        return "I couldn't find any open emergency tasks right now."
    try:
        TaskLifecycleService().accept_emergency(occurrence_id=str(occ.id), actor_id=str(user.id))
        return f"You've taken **{occ.template.name}**. The original assignee has been notified. You'll earn bonus points!"
    except Exception as exc:
        return f"Couldn't accept emergency task: {exc}"


def _handle_emergency_reassign(user, args: dict) -> str:
    occ = _find_user_occurrence(user, args.get("task_name"))
    if not occ:
        return "I couldn't find that task in your pending tasks."
    used = _emergency_reassigns_used(user)
    if used >= 3:
        return "You've used all 3 emergency reassigns this month. Try the marketplace or a swap instead."
    reason = args.get("reason") or ""
    try:
        TaskLifecycleService().emergency_reassign(
            occurrence_id=str(occ.id), actor_id=str(user.id), reason=reason
        )
        remaining = max(0, 2 - used)
        return (
            f"Emergency reassign sent for **{occ.template.name}**. "
            f"Your group has been notified. You have {remaining} emergency reassign(s) left this month."
        )
    except Exception as exc:
        return f"Couldn't emergency reassign: {exc}"


def _handle_list_marketplace(user, args: dict) -> str:
    occ = _find_user_occurrence(user, args.get("task_name"))
    if not occ:
        return "I couldn't find that task in your pending tasks."
    bonus = int(args.get("bonus_points") or 0)
    try:
        MarketplaceService().list_task(user=user, occurrence_id=str(occ.id), bonus_points=bonus)
        return f"**{occ.template.name}** is now on the marketplace. Anyone in your group can claim it."
    except (ValueError, PermissionError) as exc:
        return f"Couldn't list on marketplace: {exc}"


def _handle_request_swap(user, args: dict) -> str:
    occ = _find_user_occurrence(user, args.get("task_name"))
    if not occ:
        return "I couldn't find that task in your pending tasks."
    name   = args.get("swap_with_name", "")
    target = _find_member_by_name(user, name) if name else None
    if not target:
        return f"I couldn't find '{name}' in your groups. Try the exact name." if name else "Who would you like to swap with?"
    try:
        TaskLifecycleService().create_swap_request(
            task_id=str(occ.id), from_user_id=str(user.id),
            to_user_id=str(target.id), reason=args.get("reason") or "",
        )
        return f"Swap request sent to {_name(target)} for **{occ.template.name}**."
    except Exception as exc:
        return f"Couldn't send swap request: {exc}"


def _handle_create_group(user, args: dict) -> str:
    name = (args.get("name") or "").strip()
    if not name:
        return "What would you like to name the group?"
    try:
        group = GroupOrchestrator().create_group(owner=user, name=name)
        return f"Created group **{group.name}**! Share the join code: `{group.group_code}`"
    except Exception as exc:
        return f"Couldn't create group: {exc}"


def _handle_join_group(user, args: dict) -> str:
    code = (args.get("code") or "").strip().upper()
    if not code:
        return "What's the group code you'd like to join?"
    try:
        group = GroupOrchestrator().join_by_code(user=user, code=code)
        return f"Joined **{group.name}**!"
    except ValueError as exc:
        return str(exc)


def _handle_invite_member(user, args: dict) -> str:
    email = (args.get("email") or "").strip()
    if not email:
        return "What email address would you like to invite?"
    group = _find_group(user, args.get("group_name"))
    if not group:
        return "I couldn't find that group."
    membership = GroupMembership.objects.filter(user=user, group=group).first()
    if not membership or membership.role != 'moderator':
        return f"Only moderators can invite members to **{group.name}**."
    try:
        GroupOrchestrator().invite_member(requestor=user, group_id=str(group.id), email=email, role='member')
        return f"Invitation sent to **{email}** for **{group.name}**."
    except Exception as exc:
        return f"Couldn't send invitation: {exc}"


def _handle_delete_template(user, args: dict) -> str:
    task_name = args.get("task_name", "")
    group     = _find_group(user, args.get("group_name"))
    template  = _find_template(user, task_name, group)
    if not template:
        return f"I couldn't find a template called '{task_name}' in your groups."
    membership = GroupMembership.objects.filter(user=user, group=template.group).first()
    if not membership or membership.role != 'moderator':
        return "Only moderators can delete task templates."
    try:
        TaskTemplateService().delete_template(template_id=str(template.id), actor_id=str(user.id))
        return f"**{template.name}** has been deleted and pending occurrences cancelled."
    except Exception as exc:
        return f"Couldn't delete: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# Dispatch table
# ──────────────────────────────────────────────────────────────────────────────

_FUNCTION_HANDLERS = {
    "create_task":             _handle_create_task,
    "propose_task":            _handle_propose_task,
    "complete_task":           _handle_complete_task,
    "snooze_task":             _handle_snooze_task,
    "snooze_all_tasks":        _handle_snooze_all,
    "query_my_tasks":          _handle_query_tasks,
    "query_group_tasks":       _handle_query_group_tasks,
    "query_stats":             _handle_query_stats,
    "query_badges":            _handle_query_badges,
    "query_leaderboard":       _handle_query_leaderboard,
    "query_swap_requests":     _handle_query_swap_requests,
    "set_preference":          _handle_set_preference,
    "claim_marketplace_task":  _handle_claim_marketplace,
    "accept_swap":             _handle_accept_swap,
    "accept_emergency_task":   _handle_accept_emergency,
    "emergency_reassign_task": _handle_emergency_reassign,
    "list_task_on_marketplace":_handle_list_marketplace,
    "request_task_swap":       _handle_request_swap,
    "create_group":            _handle_create_group,
    "join_group":              _handle_join_group,
    "invite_member":           _handle_invite_member,
    "delete_task_template":    _handle_delete_template,
}


def _dispatch_function(user, name: str, args: dict) -> str:
    handler = _FUNCTION_HANDLERS.get(name)
    if not handler:
        logger.warning("Chatbot: no handler for function '%s'", name)
        return "I'm not sure how to handle that. Could you rephrase?"
    try:
        return handler(user, args)
    except Exception as exc:
        logger.exception("Chatbot dispatch error for '%s': %s", name, exc)
        return f"Something went wrong: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
# Views
# ──────────────────────────────────────────────────────────────────────────────

class ChatbotMessageAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session_id = request.query_params.get("session_id")
        if session_id:
            session = ChatbotSession.objects.filter(id=session_id, user=request.user).first()
        else:
            session = (
                ChatbotSession.objects
                .filter(user=request.user)
                .exclude(messages=[])
                .order_by('-last_active')
                .first()
            )
        if not session:
            return Response({"session_id": None, "messages": []})
        messages = [
            {"role": "user" if m["role"] == "user" else "bot", "content": m["content"]}
            for m in (session.messages or [])
        ]
        return Response({"session_id": session.id, "messages": messages})

    def post(self, request):
        message = request.data.get("message", "").strip()
        session_id = request.data.get("session_id")
        if not message:
            return Response({"error": "message required"}, status=400)

        user = request.user

        session = None
        created_session = False
        if session_id:
            session = ChatbotSession.objects.filter(id=session_id, user=user).first()
        if session is None:
            session = ChatbotSession.objects.create(user=user)
            created_session = True

        history      = session.messages[-20:]
        llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
            {"role": "user", "content": message}
        ]
        result = _call_gemini(llm_messages)

        if result is None:
            if created_session and not session.messages:
                session.delete()
            return Response({
                "reply": "The AI assistant is unavailable right now. Please try again shortly.",
                "session_id": None if created_session else session.id,
                "pending_action": False,
                "options": [],
            })

        chips = []
        if result["type"] == "function_call":
            name = result["name"]
            args = result["args"]
            logger.info("Chatbot | user=%s | session=%s | fn=%s", user.username, session.id, name)
            if name == "ask_clarification":
                reply = args.get("question", "")
                chips = args.get("chips", [])
            else:
                reply = _dispatch_function(user, name, args)
        else:
            logger.info("Chatbot | user=%s | session=%s | text response", user.username, session.id)
            reply = result.get("content") or "I'm not sure how to help with that."

        session.messages.append({"role": "user",      "content": message})
        session.messages.append({"role": "assistant",  "content": reply})
        session.pending_action = None
        session.save()

        return Response({
            "reply":          reply,
            "session_id":     session.id,
            "pending_action": bool(chips),
            "options":        chips,
        })

    def delete(self, request):
        session_id = request.data.get("session_id")
        if session_id:
            ChatbotSession.objects.filter(id=session_id, user=request.user).delete()
            logger.info("Chatbot session deleted | user=%s | session=%s", request.user.username, session_id)
        return Response({"detail": "Session cleared."})


class ChatbotSessionListAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = (
            ChatbotSession.objects
            .filter(user=request.user)
            .exclude(messages=[])
            .order_by('-last_active')[:50]
        )
        data = []
        for s in sessions:
            msgs       = s.messages or []
            first_user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
            data.append({
                "id":            s.id,
                "preview":       first_user[:80],
                "message_count": len(msgs),
                "last_active":   s.last_active.isoformat(),
            })
        return Response(data)
