"""
Chatbot router — conversational task assistant powered by Ollama + Phi-3 Mini.

Intents:
  CREATE_TASK           create a new task template + occurrences
  CANT_DO_TASK          user can't complete a task → offer emergency/marketplace/swap
  COMPLETE_TASK         mark a task as done
  SNOOZE_TASK           snooze a task
  SNOOZE_ALL            snooze all the user's pending tasks
  QUERY_MY_TASKS        list the user's pending tasks
  QUERY_GROUP_TASKS     list all tasks in a group
  QUERY_STATS           personal stats (points, streak, completion rate)
  QUERY_BADGES          earned badges
  QUERY_LEADERBOARD     group leaderboard
  QUERY_SWAP_REQUESTS   pending swap requests for the user
  SET_PREFERENCE        set prefer/neutral/avoid on a task template
  CLAIM_MARKETPLACE     claim a task from the marketplace
  ACCEPT_SWAP           accept a pending swap request
  ACCEPT_EMERGENCY      volunteer to take an emergency task
  CREATE_GROUP          create a new group
  JOIN_GROUP            join a group via code
  INVITE_MEMBER         invite someone to a group by email
  DELETE_TASK_TEMPLATE  remove a task template (moderator only)
  PROPOSE_TASK          propose a new task for group vote
  CHOOSE_OPTION         reply to a multi-turn prompt
  UNKNOWN               fallback
"""
from __future__ import annotations

import httpx
import json
import logging
from datetime import timedelta

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
    TaskAssignmentHistory, TaskOccurrence, TaskPreference, TaskSwap,
    TaskTemplate, UserStats, UserBadge,
)
from chore_sync.services.task_lifecycle_service import TaskLifecycleService
from chore_sync.services.task_template_service import TaskTemplateService
from chore_sync.services.marketplace_service import MarketplaceService
from chore_sync.services.group_service import GroupOrchestrator
from chore_sync.services.proposal_service import ProposalService

OLLAMA_URL = getattr(settings, 'OLLAMA_URL', 'http://localhost:11434/api/chat')
MODEL = getattr(settings, 'OLLAMA_MODEL', 'phi3:mini')
DAY_INT_TO_ABBR = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}
DAY_NAME_TO_INT = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
    'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6,
}

# ──────────────────────────────────────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a task assistant for ChoreSync, a household chore app.
Understand the user's message and return ONLY a JSON object — no explanation, no markdown.

Possible intents and JSON shapes:

CREATE_TASK: {"intent":"CREATE_TASK","name":"str","recurrence":"weekly|monthly|once","day_of_week":"monday|tuesday|wednesday|thursday|friday|saturday|sunday|null","estimated_minutes":int_or_null,"difficulty":1-5_or_null,"category":"cleaning|cooking|laundry|maintenance|other","assign_to_name":"str_or_null"}
CANT_DO_TASK: {"intent":"CANT_DO_TASK","task_name":"str_or_null","reason":"str_or_null"}
COMPLETE_TASK: {"intent":"COMPLETE_TASK","task_name":"str_or_null"}
SNOOZE_TASK: {"intent":"SNOOZE_TASK","task_name":"str_or_null","snooze_hours":int_or_null}
SNOOZE_ALL: {"intent":"SNOOZE_ALL","snooze_hours":int_or_null}
QUERY_MY_TASKS: {"intent":"QUERY_MY_TASKS"}
QUERY_GROUP_TASKS: {"intent":"QUERY_GROUP_TASKS","group_name":"str_or_null"}
QUERY_STATS: {"intent":"QUERY_STATS"}
QUERY_BADGES: {"intent":"QUERY_BADGES"}
QUERY_LEADERBOARD: {"intent":"QUERY_LEADERBOARD","group_name":"str_or_null"}
QUERY_SWAP_REQUESTS: {"intent":"QUERY_SWAP_REQUESTS"}
SET_PREFERENCE: {"intent":"SET_PREFERENCE","task_name":"str","preference":"prefer|neutral|avoid"}
CLAIM_MARKETPLACE: {"intent":"CLAIM_MARKETPLACE","task_name":"str_or_null","group_name":"str_or_null"}
ACCEPT_SWAP: {"intent":"ACCEPT_SWAP","task_name":"str_or_null"}
ACCEPT_EMERGENCY: {"intent":"ACCEPT_EMERGENCY","task_name":"str_or_null"}
CREATE_GROUP: {"intent":"CREATE_GROUP","name":"str"}
JOIN_GROUP: {"intent":"JOIN_GROUP","code":"str"}
INVITE_MEMBER: {"intent":"INVITE_MEMBER","email":"str","group_name":"str_or_null"}
DELETE_TASK_TEMPLATE: {"intent":"DELETE_TASK_TEMPLATE","task_name":"str","group_name":"str_or_null"}
PROPOSE_TASK: {"intent":"PROPOSE_TASK","task_name":"str","reason":"str_or_null","group_name":"str_or_null"}
CHOOSE_OPTION: {"intent":"CHOOSE_OPTION","choice":"str"}
UNKNOWN: {"intent":"UNKNOWN"}

Rules:
- Return ONLY the JSON object.
- day_of_week: use the full day name in lowercase, e.g. "monday", "friday". Use null if no specific day.
- "I can't do X", "I'm sick", "I won't be able to" → CANT_DO_TASK
- "I've done X", "mark X complete", "finished X" → COMPLETE_TASK
- "I hate X", "I love doing X", "avoid X" → SET_PREFERENCE
- "What's on the marketplace" / "I'll take [task]" → CLAIM_MARKETPLACE
- "Accept [name]'s swap" / "accept the swap request" → ACCEPT_SWAP
- "I'll help with [name]'s emergency" → ACCEPT_EMERGENCY
- "Snooze all my tasks" → SNOOZE_ALL
- User replying to options you presented → CHOOSE_OPTION"""


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _call_ollama(messages: list[dict]) -> dict | None:
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    logger.debug("Chatbot → Ollama | model=%s | messages=%d", MODEL, len(messages))
    try:
        resp = httpx.post(OLLAMA_URL, json=payload, timeout=60)
    except httpx.RequestError as exc:
        logger.error("Chatbot Ollama request error: %s", exc)
        return None
    if not resp.is_success:
        logger.error("Chatbot Ollama HTTP %s: %s", resp.status_code, resp.text[:200])
        return None
    body = resp.json()
    raw = body.get("message", {}).get("content", "").strip()
    logger.debug("Chatbot ← Ollama raw: %s", raw[:300])
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Chatbot JSON parse failed. Raw: %s", raw[:300])
        return None


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
    qs = GroupMembership.objects.filter(user=user).select_related('group')
    if not group_name:
        m = qs.first()
        return m.group if m else None
    low = group_name.lower()
    for m in qs:
        if low in m.group.name.lower():
            return m.group
    return None


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


def _compute_next_due(recurrence: str, day_of_week: int | None):
    base = timezone.now().replace(hour=20, minute=0, second=0, microsecond=0)
    if recurrence == 'once' or day_of_week is None:
        return base + timedelta(days=1)
    return base


# ──────────────────────────────────────────────────────────────────────────────
# Intent handlers
# ──────────────────────────────────────────────────────────────────────────────

def _handle_create_task(user, parsed: dict) -> tuple[str, None]:
    recurrence = parsed.get("recurrence", "weekly")
    raw_day = parsed.get("day_of_week")
    # Normalise: LLM may return a name ("monday"), an int, or null
    if isinstance(raw_day, str):
        day_of_week = DAY_NAME_TO_INT.get(raw_day.lower().strip())
    elif isinstance(raw_day, int) and 0 <= raw_day <= 6:
        day_of_week = raw_day
    else:
        day_of_week = None

    if recurrence == "once":
        recurring_choice, days_of_week = "none", None
    elif day_of_week is not None:
        recurring_choice, days_of_week = "custom", [DAY_INT_TO_ABBR[day_of_week]]
    else:
        recurring_choice, days_of_week = "weekly", None

    group = _find_group(user, None)
    if not group:
        return "You're not in any group yet. Create or join a group first.", None

    payload = {
        "name": parsed.get("name", "New Task"),
        "recurring_choice": recurring_choice,
        "days_of_week": days_of_week,
        "estimated_mins": parsed.get("estimated_minutes") or 30,
        "difficulty": parsed.get("difficulty") or 2,
        "category": parsed.get("category", "other"),
        "next_due": _compute_next_due(recurrence, day_of_week),
    }
    try:
        template = TaskTemplateService().create_template(
            creator=user,
            group_id=str(group.id),
            payload=payload,
        )
    except ValueError as exc:
        return f"Couldn't create task: {exc}", None
    TaskLifecycleService().generate_recurring_instances(task_template_id=str(template.id))

    day_str = f" on {['Mondays','Tuesdays','Wednesdays','Thursdays','Fridays','Saturdays','Sundays'][day_of_week]}" if day_of_week is not None else ""
    return f"Done! Created **{template.name}** ({recurrence}{day_str}) in {group.name}.", None


def _handle_cant_do_task(user, parsed: dict) -> tuple[str, dict | None]:
    occ = _find_user_occurrence(user, parsed.get("task_name"))
    if not occ:
        return f"I couldn't find that task in your pending tasks. Could you be more specific?", None
    used = _emergency_reassigns_used(user)
    remaining = max(0, 3 - used)
    reason = parsed.get("reason") or "personal reasons"
    lines = [
        f"Here's what you can do with **{occ.template.name}** (due {occ.deadline.strftime('%a %d %b, %H:%M')}):",
        "",
        f"1. **Emergency reassign** — broadcast to your group ({remaining}/3 remaining this month)",
        "2. **List on marketplace** — anyone in the group can claim it",
        "3. **Swap** — request a swap with someone (e.g. 'swap with Jamie')",
        "",
        "Reply with 1, 2, 3, or describe what you'd like.",
    ]
    return "\n".join(lines), {"intent": "CANT_DO_TASK", "occurrence_id": occ.id, "reason": reason}


def _handle_complete_task(user, parsed: dict) -> tuple[str, None]:
    occ = _find_user_occurrence(user, parsed.get("task_name"))
    if not occ:
        return "I couldn't find that task in your pending tasks.", None
    try:
        TaskLifecycleService().toggle_occurrence_completed(
            occurrence_id=str(occ.id), actor_id=str(user.id)
        )
        return f"Marked **{occ.template.name}** as complete!", None
    except Exception as e:
        return f"Couldn't complete that task: {e}", None


def _handle_snooze_task(user, parsed: dict) -> tuple[str, None]:
    occ = _find_user_occurrence(user, parsed.get("task_name"))
    if not occ:
        return "I couldn't find that task in your pending tasks.", None
    hours = parsed.get("snooze_hours") or 3
    snooze_until = timezone.now() + timedelta(hours=hours)
    try:
        TaskLifecycleService().snooze_task(
            occurrence_id=str(occ.id), snooze_until=snooze_until, actor_id=str(user.id)
        )
        return f"Snoozed **{occ.template.name}** for {hours}h (until {snooze_until.strftime('%H:%M')}).", None
    except Exception as e:
        return f"Couldn't snooze: {e}", None


def _handle_snooze_all(user, parsed: dict) -> tuple[str, None]:
    hours = parsed.get("snooze_hours") or 3
    snooze_until = timezone.now() + timedelta(hours=hours)
    svc = TaskLifecycleService()
    occs = list(TaskOccurrence.objects.filter(
        assigned_to=user, status='pending'
    ).select_related('template'))
    if not occs:
        return "You have no pending tasks to snooze.", None
    succeeded = 0
    failed_names: list[str] = []
    for occ in occs:
        try:
            svc.snooze_task(
                occurrence_id=str(occ.id), snooze_until=snooze_until, actor_id=str(user.id)
            )
            succeeded += 1
        except Exception as exc:
            failed_names.append(occ.template.name)
            logger.warning(
                "Chatbot snooze_all: failed to snooze occurrence %s (%s) for user %s: %s",
                occ.id, occ.template.name, user.id, exc,
            )
    if succeeded == 0:
        return "Couldn't snooze any tasks right now. Please try again.", None
    msg = f"Snoozed {succeeded} task(s) for {hours}h (until {snooze_until.strftime('%H:%M')})."
    if failed_names:
        msg += f" ⚠️ Could not snooze: {', '.join(failed_names)}."
    return msg, None


def _handle_query_tasks(user) -> tuple[str, None]:
    occs = TaskOccurrence.objects.filter(
        assigned_to=user, status__in=['pending', 'snoozed']
    ).select_related('template').order_by('deadline')[:10]
    if not occs:
        return "You have no pending tasks right now.", None
    lines = [f"Your pending tasks ({len(occs)}):"]
    for occ in occs:
        suffix = " *(snoozed)*" if occ.status == 'snoozed' else ""
        lines.append(f"• **{occ.template.name}** — due {occ.deadline.strftime('%a %d %b, %H:%M')}{suffix}")
    return "\n".join(lines), None


def _handle_query_group_tasks(user, parsed: dict) -> tuple[str, None]:
    group = _find_group(user, parsed.get("group_name"))
    if not group:
        return "I couldn't find that group.", None
    occs = TaskOccurrence.objects.filter(
        template__group=group, status__in=['pending', 'snoozed', 'overdue']
    ).select_related('template', 'assigned_to').order_by('deadline')[:15]
    if not occs:
        return f"No pending tasks in **{group.name}**.", None
    lines = [f"Tasks in **{group.name}**:"]
    for occ in occs:
        assignee = _name(occ.assigned_to) if occ.assigned_to else "Unassigned"
        lines.append(f"• **{occ.template.name}** — {assignee}, due {occ.deadline.strftime('%a %d %b')}")
    return "\n".join(lines), None


def _handle_query_stats(user) -> tuple[str, None]:
    memberships = GroupMembership.objects.filter(user=user).select_related('group')
    if not memberships:
        return "You're not in any group yet.", None
    lines = [f"Stats for **{_name(user)}**:"]
    for m in memberships:
        s = UserStats.objects.filter(user=user, household=m.group).first()
        if s:
            lines.append(
                f"\n**{m.group.name}:** {s.total_tasks_completed} tasks · "
                f"{s.total_points} pts · {s.current_streak_days}-day streak · "
                f"{round(s.on_time_completion_rate * 100)}% on time"
            )
    return "\n".join(lines), None


def _handle_query_badges(user) -> tuple[str, None]:
    badges = UserBadge.objects.filter(user=user).select_related('badge').order_by('-awarded_at')[:10]
    if not badges:
        return "You haven't earned any badges yet. Complete tasks to start earning!", None
    lines = [f"Your badges ({badges.count()}):"]
    for ub in badges:
        lines.append(f"• **{ub.badge.name}** — {ub.badge.description}")
    return "\n".join(lines), None


def _handle_query_leaderboard(user, parsed: dict) -> tuple[str, None]:
    group = _find_group(user, parsed.get("group_name"))
    if not group:
        return "I couldn't find that group.", None
    stats = UserStats.objects.filter(
        household=group
    ).select_related('user').order_by('-total_points')[:8]
    if not stats:
        return f"No leaderboard data yet for **{group.name}**.", None
    lines = [f"Leaderboard — **{group.name}**:"]
    for i, s in enumerate(stats, 1):
        marker = " ← you" if s.user_id == user.id else ""
        lines.append(
            f"{i}. {_name(s.user)} — {s.total_points} pts · "
            f"{s.current_streak_days}-day streak{marker}"
        )
    return "\n".join(lines), None


def _handle_query_swap_requests(user) -> tuple[str, None]:
    swaps = TaskSwap.objects.filter(
        to_user=user, status='pending'
    ).select_related('task__template', 'from_user').order_by('expires_at')
    if not swaps:
        return "You have no pending swap requests.", None
    lines = [f"Pending swap requests ({swaps.count()}):"]
    for sw in swaps:
        expires = sw.expires_at.strftime('%a %d %b') if sw.expires_at else "soon"
        lines.append(
            f"• **{sw.task.template.name}** from {_name(sw.from_user)} "
            f"— expires {expires} (swap ID: {sw.id})"
        )
    lines.append("\nSay 'accept [task name] swap' to accept one.")
    return "\n".join(lines), None


def _handle_set_preference(user, parsed: dict) -> tuple[str, None]:
    task_name = parsed.get("task_name", "")
    preference = parsed.get("preference", "neutral")
    template = _find_template(user, task_name)
    if not template:
        return f"I couldn't find a task called '{task_name}' in your groups.", None
    obj, _ = TaskPreference.objects.update_or_create(
        user=user, task_template=template,
        defaults={"preference": preference},
    )
    verb = {"prefer": "You'll be prioritised for", "avoid": "You'll be deprioritised for", "neutral": "You're neutral on"}[preference]
    return f"{verb} **{template.name}**. Preference saved.", None


def _handle_claim_marketplace(user, parsed: dict) -> tuple[str, None]:
    group = _find_group(user, parsed.get("group_name"))
    if not group:
        return "I couldn't find that group.", None

    task_name = parsed.get("task_name")
    listings = MarketplaceListing.objects.filter(
        task_occurrence__template__group=group,
        expires_at__gt=timezone.now(),
    ).select_related('task_occurrence__template', 'listed_by')

    if not listings:
        return f"There's nothing on the marketplace in **{group.name}** right now.", None

    if not task_name:
        lines = [f"Marketplace listings in **{group.name}**:"]
        for l in listings[:8]:
            bonus = f" (+{l.bonus_points} pts)" if l.bonus_points else ""
            lines.append(f"• **{l.task_occurrence.template.name}**{bonus} — listed by {_name(l.listed_by)}")
        lines.append("\nSay 'claim [task name]' to take one.")
        return "\n".join(lines), None

    low = task_name.lower()
    match = next((l for l in listings if low in l.task_occurrence.template.name.lower()), None)
    if not match:
        return f"I couldn't find '{task_name}' on the marketplace.", None

    try:
        MarketplaceService().claim_task(user=user, listing_id=match.id)
        bonus_str = f" You earned +{match.bonus_points} bonus points!" if match.bonus_points else ""
        return f"Claimed **{match.task_occurrence.template.name}**!{bonus_str}", None
    except Exception as e:
        return f"Couldn't claim that task: {e}", None


def _handle_accept_swap(user, parsed: dict) -> tuple[str, None]:
    task_name = parsed.get("task_name")
    qs = TaskSwap.objects.filter(to_user=user, status='pending').select_related('task__template')
    if task_name:
        low = task_name.lower()
        swap = next((s for s in qs if low in s.task.template.name.lower()), None)
    else:
        swap = qs.order_by('expires_at').first()

    if not swap:
        return "I couldn't find a pending swap request for that task.", None
    try:
        TaskLifecycleService().respond_to_swap_request(
            swap_id=str(swap.id), accept=True, actor_id=str(user.id)
        )
        return f"Accepted the swap for **{swap.task.template.name}**. It's now yours.", None
    except Exception as e:
        return f"Couldn't accept swap: {e}", None


def _handle_accept_emergency(user, parsed: dict) -> tuple[str, None]:
    task_name = parsed.get("task_name")
    # Emergency occurrences: reassignment_reason='emergency', no current assignee
    qs = TaskOccurrence.objects.filter(
        status='pending',
        reassignment_reason='emergency',
        assigned_to__isnull=True,
        template__group__in=GroupMembership.objects.filter(user=user).values('group'),
    ).select_related('template')
    if task_name:
        low = task_name.lower()
        occ = next((o for o in qs if low in o.template.name.lower()), None)
    else:
        occ = qs.order_by('deadline').first()

    if not occ:
        return "I couldn't find any open emergency tasks right now.", None
    try:
        TaskLifecycleService().accept_emergency(
            occurrence_id=str(occ.id), actor_id=str(user.id)
        )
        return f"You've taken **{occ.template.name}**. The original assignee has been notified. You'll earn bonus points!", None
    except Exception as e:
        return f"Couldn't accept emergency task: {e}", None


def _handle_create_group(user, parsed: dict) -> tuple[str, None]:
    name = parsed.get("name", "").strip()
    if not name:
        return "What would you like to name the group?", None
    try:
        group = GroupOrchestrator().create_group(owner=user, name=name)
        return f"Created group **{group.name}**! Share the join code: `{group.group_code}`", None
    except Exception as e:
        return f"Couldn't create group: {e}", None


def _handle_join_group(user, parsed: dict) -> tuple[str, None]:
    code = (parsed.get("code") or "").strip().upper()
    if not code:
        return "What's the group code you'd like to join?", None
    try:
        group = GroupOrchestrator().join_by_code(user=user, code=code)
        return f"Joined **{group.name}**!", None
    except ValueError as e:
        return str(e), None


def _handle_invite_member(user, parsed: dict) -> tuple[str, None]:
    email = parsed.get("email", "").strip()
    if not email:
        return "What email address would you like to invite?", None
    group = _find_group(user, parsed.get("group_name"))
    if not group:
        return "I couldn't find that group.", None
    membership = GroupMembership.objects.filter(user=user, group=group).first()
    if not membership or membership.role != 'moderator':
        return f"Only moderators can invite members to **{group.name}**.", None
    try:
        GroupOrchestrator().invite_member(
            requestor=user, group_id=str(group.id), email=email, role='member'
        )
        return f"Invitation sent to **{email}** for **{group.name}**.", None
    except Exception as e:
        return f"Couldn't send invitation: {e}", None


def _handle_delete_template(user, parsed: dict) -> tuple[str, dict | None]:
    from chore_sync.services.task_template_service import TaskTemplateService
    task_name = parsed.get("task_name", "")
    group = _find_group(user, parsed.get("group_name"))
    template = _find_template(user, task_name, group)
    if not template:
        return f"I couldn't find a template called '{task_name}' in your groups.", None
    membership = GroupMembership.objects.filter(user=user, group=template.group).first()
    if not membership or membership.role != 'moderator':
        return f"Only moderators can delete task templates.", None
    # Confirm before deleting
    return (
        f"Are you sure you want to delete **{template.name}** from **{template.group.name}**? "
        f"This will cancel all pending occurrences. Reply 'yes, delete it' to confirm.",
        {"intent": "DELETE_TASK_TEMPLATE", "template_id": template.id, "template_name": template.name},
    )


def _handle_propose_task(user, parsed: dict) -> tuple[str, None]:
    task_name = parsed.get("task_name", "")
    group = _find_group(user, parsed.get("group_name"))
    if not group:
        return "I couldn't find that group.", None
    template = _find_template(user, task_name, group)
    if not template:
        return f"I couldn't find a template called '{task_name}'. Proposals are for existing templates.", None
    reason = parsed.get("reason") or ""
    try:
        ProposalService().create_proposal(
            proposer_id=str(user.id),
            group_id=str(group.id),
            task_template_id=template.id,
            reason=reason,
        )
        return f"Proposal submitted for **{template.name}** in **{group.name}**. Group members can now vote.", None
    except (ValueError, PermissionError) as e:
        return f"Couldn't submit proposal: {e}", None


def _handle_choose_option(user, choice: str, pending: dict) -> tuple[str, dict | None]:
    intent = pending.get("intent")

    if intent == "CANT_DO_TASK":
        occ_id = pending.get("occurrence_id")
        reason = pending.get("reason", "")
        try:
            occ = TaskOccurrence.objects.select_related('template').get(id=occ_id)
        except TaskOccurrence.DoesNotExist:
            return "That task no longer exists.", None

        low = choice.lower()

        if any(x in low for x in ["1", "emergency"]):
            used = _emergency_reassigns_used(user)
            if used >= 3:
                return "You've used all 3 emergency reassigns this month. Try the marketplace or a swap instead.", None
            try:
                TaskLifecycleService().emergency_reassign(
                    occurrence_id=str(occ_id), actor_id=str(user.id), reason=reason
                )
                remaining = max(0, 2 - used)
                return (
                    f"Emergency reassign sent for **{occ.template.name}**. "
                    f"Your group has been notified. You have {remaining} emergency reassign(s) left this month.", None
                )
            except Exception as e:
                return f"Couldn't emergency reassign: {e}", None

        if any(x in low for x in ["2", "marketplace", "market"]):
            try:
                MarketplaceService().list_task(
                    user=user,
                    occurrence_id=str(occ_id),
                    bonus_points=0,
                )
                return f"**{occ.template.name}** is now on the marketplace. Anyone in your group can claim it.", None
            except (ValueError, PermissionError) as e:
                return f"Couldn't list on marketplace: {e}", None

        if any(x in low for x in ["3", "swap"]):
            name = None
            if "with" in low:
                name = choice.split("with", 1)[1].strip().title()
            if name:
                target = _find_member_by_name(user, name)
                if target:
                    try:
                        TaskLifecycleService().create_swap_request(
                            task_id=str(occ_id), from_user_id=str(user.id),
                            to_user_id=str(target.id), reason=reason,
                        )
                        return f"Swap request sent to {_name(target)} for **{occ.template.name}**.", None
                    except Exception as e:
                        return f"Couldn't send swap request: {e}", None
                else:
                    return f"I couldn't find '{name}' in your groups. Try the exact name.", None
            else:
                return "Who would you like to swap with? Say 'swap with [name]'.", pending

    if intent == "DELETE_TASK_TEMPLATE":
        if any(x in choice.lower() for x in ["yes", "confirm", "delete"]):
            from chore_sync.services.task_template_service import TaskTemplateService
            template_id = pending.get("template_id")
            template_name = pending.get("template_name", "that template")
            try:
                TaskTemplateService().delete_template(
                    template_id=str(template_id), actor_id=str(user.id)
                )
                return f"**{template_name}** has been deleted and pending occurrences cancelled.", None
            except Exception as e:
                return f"Couldn't delete: {e}", None
        else:
            return "Deletion cancelled.", None

    return "I'm not sure what to do with that reply. Could you rephrase?", None


# ──────────────────────────────────────────────────────────────────────────────
# View
# ──────────────────────────────────────────────────────────────────────────────

INTENT_HANDLERS = {
    "CREATE_TASK": lambda user, p: _handle_create_task(user, p),
    "CANT_DO_TASK": lambda user, p: _handle_cant_do_task(user, p),
    "COMPLETE_TASK": lambda user, p: _handle_complete_task(user, p),
    "SNOOZE_TASK": lambda user, p: _handle_snooze_task(user, p),
    "SNOOZE_ALL": lambda user, p: _handle_snooze_all(user, p),
    "QUERY_MY_TASKS": lambda user, p: _handle_query_tasks(user),
    "QUERY_GROUP_TASKS": lambda user, p: _handle_query_group_tasks(user, p),
    "QUERY_STATS": lambda user, p: _handle_query_stats(user),
    "QUERY_BADGES": lambda user, p: _handle_query_badges(user),
    "QUERY_LEADERBOARD": lambda user, p: _handle_query_leaderboard(user, p),
    "QUERY_SWAP_REQUESTS": lambda user, p: _handle_query_swap_requests(user),
    "SET_PREFERENCE": lambda user, p: _handle_set_preference(user, p),
    "CLAIM_MARKETPLACE": lambda user, p: _handle_claim_marketplace(user, p),
    "ACCEPT_SWAP": lambda user, p: _handle_accept_swap(user, p),
    "ACCEPT_EMERGENCY": lambda user, p: _handle_accept_emergency(user, p),
    "CREATE_GROUP": lambda user, p: _handle_create_group(user, p),
    "JOIN_GROUP": lambda user, p: _handle_join_group(user, p),
    "INVITE_MEMBER": lambda user, p: _handle_invite_member(user, p),
    "DELETE_TASK_TEMPLATE": lambda user, p: _handle_delete_template(user, p),
    "PROPOSE_TASK": lambda user, p: _handle_propose_task(user, p),
}

UNKNOWN_REPLY = (
    "I didn't quite understand that. Here's what I can help with:\n\n"
    "**Tasks:** 'What tasks do I have?' · 'I've done the vacuuming' · 'Snooze dishes for 3 hours'\n"
    "**Can't do a task:** 'I can't do bathroom cleaning today, I'm sick'\n"
    "**Preferences:** 'I hate vacuuming' · 'I love doing dishes'\n"
    "**Marketplace:** 'What's on the marketplace?' · 'Claim the bathroom task'\n"
    "**Swaps:** 'Accept Jamie's swap request'\n"
    "**Stats:** 'How am I doing?' · 'Show the leaderboard' · 'What badges do I have?'\n"
    "**Groups:** 'Create a group called Flat 3' · 'Join group ABC123' · 'Invite bob@email.com'\n"
    "**Create task:** 'Add weekly bathroom cleaning on Fridays'"
)


class ChatbotMessageAPIView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return a session's message history.
        ?session_id=<id> → load that specific session.
        No param           → load the most recent non-empty session.
        """
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

        # Load or create session
        session = None
        created_session = False
        if session_id:
            session = ChatbotSession.objects.filter(id=session_id, user=user).first()
        if session is None:
            session = ChatbotSession.objects.create(user=user)
            created_session = True

        # Multi-turn: if pending action, parse choice locally without Ollama
        if session.pending_action:
            parsed = {"intent": "CHOOSE_OPTION", "choice": message}
        else:
            history = session.messages[-20:]
            ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
                {"role": "user", "content": message}
            ]
            parsed = _call_ollama(ollama_messages)
            if parsed is None:
                if created_session and not session.messages and not session.pending_action:
                    session.delete()
                return Response({
                    "reply": "The AI assistant is unavailable right now. Please try again shortly.",
                    "session_id": None if created_session else session.id,
                    "pending_action": False,
                })

        intent = parsed.get("intent", "UNKNOWN")
        logger.info("Chatbot | user=%s | session=%s | intent=%s", user.username, session.id, intent)
        next_pending = None

        if intent == "CHOOSE_OPTION" and session.pending_action:
            reply, next_pending = _handle_choose_option(user, message, session.pending_action)
        elif intent in INTENT_HANDLERS:
            reply, next_pending = INTENT_HANDLERS[intent](user, parsed)
        else:
            reply = UNKNOWN_REPLY

        # Persist history only for non-pending-reply turns
        if not session.pending_action:
            session.messages.append({"role": "user", "content": message})
            session.messages.append({"role": "assistant", "content": reply})

        session.pending_action = next_pending
        session.save()

        return Response({
            "reply": reply,
            "session_id": session.id,
            "pending_action": bool(next_pending),
        })

    def delete(self, request):
        session_id = request.data.get("session_id")
        if session_id:
            ChatbotSession.objects.filter(id=session_id, user=request.user).delete()
            logger.info("Chatbot session deleted | user=%s | session=%s", request.user.username, session_id)
        return Response({"detail": "Session cleared."})


class ChatbotSessionListAPIView(APIView):
    """GET /api/assistant/sessions/ — list all non-empty sessions for the current user."""
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
            msgs = s.messages or []
            # First user message as preview title
            first_user = next((m["content"] for m in msgs if m.get("role") == "user"), "")
            data.append({
                "id": s.id,
                "preview": first_user[:80],
                "message_count": len(msgs),
                "last_active": s.last_active.isoformat(),
            })
        return Response(data)
