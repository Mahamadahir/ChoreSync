# ChoreSync: Gap Analysis & Technical Implementation Roadmap

---

## Executive Summary: Current State vs. Goal

**Goal:** A complete household chore coordination platform with smart assignment, gamification, real-time collaboration, and two-way calendar sync — built on Django + DRF + Django Channels + Vue.js.

**Current State:** The project has a well-structured skeleton with strong foundations in authentication and Google Calendar OAuth, but the core product logic — task management, group operations, notifications, gamification — consists entirely of stub classes that `raise NotImplementedError`. The backend has a critical architectural fracture: task and group routers were built with **FastAPI** but the application runs on **Django**, leaving them dead code. The data models are partially aligned with the plan but have significant field-level gaps. Approximately **~15% of the planned functionality is implemented end-to-end.**

---

## Critical Architectural Problems (Must Fix First)

### Problem 1: Framework Schism (Blocker)
`backend/chore_sync/api/task_router.py`, `group_router.py`, `auth_router.py`, and `calendar_router.py` use `from fastapi import APIRouter`. The application runs Django. These routers are **never registered** in `backend/chore_sync/urls.py` (see the `# TODO: add group/task endpoints` comment on line 67). Every endpoint in these files is unreachable dead code. Additionally, `backend/chore_sync/apps.py` defines a FastAPI application that is never used (Django uses `wsgi.py`/`asgi.py`). Furthermore, three calendar-related stub services (`calendar_service.py`, `calendar_event_service.py`, `calendar_auth_service.py`) duplicate logic already implemented in `google_calendar_service.py`.

### Problem 2: WebSocket vs. SSE
The plan specifies **Django Channels** for WebSockets. The codebase implements **Server-Sent Events** (`backend/chore_sync/sse.py`) — one-directional only. Real-time features like live chat, emergency reassign broadcast, and leaderboard push are architecturally blocked without adding Django Channels.

### Problem 3: Default Permission is AllowAny
`backend/chore_sync/settings.py` line 154 sets `DEFAULT_PERMISSION_CLASSES = ["rest_framework.permissions.AllowAny"]`. Every API endpoint is publicly accessible by default. This must be reversed to `IsAuthenticated` with opt-in public routes.

### Problem 4: OAuth Tokens Stored Unencrypted
`backend/chore_sync/models.py` line 319 — `ExternalCredential.secret` is a plain `JSONField`. A database breach exposes every user's Google/Microsoft access token. The `TODO: Encrypt this field before production` comment exists but is unaddressed.

---

## Gap Table

| Feature | Status | Required Changes |
|---|---|---|
| User Registration / Login | **Implemented** | Minor: default permission class is AllowAny globally |
| Email Verification | **Implemented** | None |
| Password Reset | **Implemented** | None |
| Google OAuth Login | **Implemented** | None |
| Microsoft OAuth Login | **Partial** — view exists, provider stub unclear | Verify `microsoft_provider.py` implementation |
| Google Calendar OAuth + Sync | **Implemented** | Token encryption missing |
| Outlook Calendar Sync | **Partial** — provider file exists | Audit `microsoft_provider.py` for NotImplementedError |
| Group (Household) Creation | **Pending** | Rewrite `group_router.py` in DRF; implement `GroupOrchestrator.create_group` |
| Group Member Invitation | **Pending** | Implement invite flow with token + email |
| Group Settings (fairness algo, photo proof, voting) | **Pending** | Add missing fields to `Group` model; create settings endpoint |
| TaskTemplate CRUD | **Pending** | All `TaskTemplateService` methods are stubs; no DRF endpoints |
| TaskOccurrence Creation | **Pending** | `TaskScheduler.schedule_task` is a stub |
| Recurring Task Generation | **Pending** | `generate_recurring_instances` is a stub; Celery periodic task missing |
| Smart Assignment Algorithm | **Pending** | `compute_candidate_scores` + `select_assignee` both stubs; no fairness mode in Group model |
| Task Completion Tracking | **Pending** | `toggle_occurrence_completed` is a stub; `status` field missing from TaskOccurrence |
| Snooze ("I'll Do It Later") | **Pending** | `snooze_until` field missing from TaskOccurrence model; endpoint missing |
| Emergency Reassign | **Pending** | No model field, no endpoint, no WebSocket broadcast |
| Task Swaps | **Partial** — `TaskSwap` model exists | `TaskLifecycleService.create_swap_request` is a stub; no endpoint; no expiry field |
| Task Marketplace | **Pending** | No model, no endpoint |
| Task Preferences | **Partial** — `TaskPreference` model exists (3-level) | Plan requires -2 to +2 numeric scale; no endpoint to set preferences |
| Deadline Reminder System | **Pending** | No Celery periodic tasks; `NotificationService` all stubs |
| Notification Delivery | **Pending** | All `NotificationService` methods are stubs |
| In-App Notifications (read/dismiss) | **Partial** — `Notification` model exists | No API endpoints; missing `title`, `action_url`, `sent_at` fields |
| Real-Time WebSocket Events | **Pending** | Django Channels not installed; SSE is unidirectional |
| Real-Time Chat | **Partial** — `Message` + `MessageReceipt` models exist | No WebSocket; no chat endpoint |
| Streaks | **Partial** — fields on `User` model | No calculation logic, no Celery job to update |
| Points System | **Pending** | No points field on `TaskOccurrence`; no calculation logic |
| Leaderboard | **Pending** | No `UserStats` model; no endpoint; no calculation job |
| Badges | **Pending** | No `Badge` or `UserBadge` model; no awarding logic |
| Photo Proof | **Pending** | No `photo_proof` field on TaskOccurrence; no upload endpoint |
| Stats Dashboard (API) | **Pending** | No endpoints; no `UserStats` model |
| Smart Suggestions | **Pending** | No model, no background job, no endpoint |
| Task Proposal Voting | **Partial** — `TaskProposal` + `TaskVote` models exist | `proposal_service.py` (stub assumed); no endpoints registered |
| Group Assignment Matrix | **Pending** | `compute_assignment_matrix` is a stub |
| Celery Background Jobs | **Partial** — configured; 1 task (email) | No periodic tasks: recurrence gen, reminder dispatch, badge awards, leaderboard |
| Frontend Group Management UI | **Pending** | Controllers deleted (never imported); must implement after backend API is ready |
| Frontend Task Board | **Pending** | TaskBoard.ts deleted (never imported); must implement after backend API is ready |
| Frontend Notifications UI | **Pending** | Controllers deleted (never imported); must implement after backend API is ready |
| Frontend Chat UI | **Pending** | Controllers deleted (never imported); must implement after backend WebSocket is ready |
| PWA Configuration | **Pending** | No `manifest.json`, no service worker |
| Rate Limiting | **Pending** | `django-ratelimit` not in dependencies |
| OAuth Token Encryption | **Pending** (Security) | `ExternalCredential.secret` is plaintext JSON |
| JWT Authentication | **Pending** | Plan specifies JWT; code uses session auth |

---

## Step-by-Step Implementation Roadmap

---

### Step 1: Fix Architecture ✅ COMPLETE

**Files:** `backend/chore_sync/settings.py`, `backend/chore_sync/api/*.py`, `backend/chore_sync/urls.py`, `backend/pyproject.toml`, `frontend/src/**/*.{ts,vue}`

**Actions:**

**1a. Delete Dead Code (FastAPI Schism):**
- Delete `backend/chore_sync/apps.py` (FastAPI app never used)
- Delete `backend/chore_sync/api/task_router.py`
- Delete `backend/chore_sync/api/group_router.py`
- Delete `backend/chore_sync/api/auth_router.py`
- Delete `backend/chore_sync/api/calendar_router.py`
- Delete `backend/chore_sync/tests/test_task_router.py`
- Delete `backend/chore_sync/tests/test_group_router.py`
- Delete `backend/chore_sync/tests/test_calendar_router.py`
- Delete `backend/chore_sync/repositories/` directory (empty, unused)
- Remove `fastapi` and `uvicorn` from `backend/pyproject.toml` dependencies

**1b. Delete Orphaned Services (Out of Scope):**
- Delete `backend/chore_sync/services/nudge_service.py` (not in plan)
- Delete `backend/chore_sync/services/guest_access_service.py` (not in plan)
- Delete `backend/chore_sync/services/playbook_service.py` (not in plan)
- Delete `backend/chore_sync/services/inventory_service.py` (not in plan)
- Delete corresponding test files: `test_nudge_service.py`, `test_guest_access_service.py`, `test_playbook_service.py`, `test_inventory_service.py`

**1c. Delete Redundant Calendar Stubs (Duplicated by google_calendar_service.py):**
- Delete `backend/chore_sync/services/calendar_service.py` (CalendarSyncService)
- Delete `backend/chore_sync/services/calendar_event_service.py` (CalendarEventService)
- Delete `backend/chore_sync/services/calendar_auth_service.py` (CalendarAuthService)
- Delete corresponding test files: `test_calendar_service.py`, `test_calendar_event_service.py`, `test_calendar_auth_service.py`
- **Note:** `google_calendar_service.py` (GoogleCalendarService) is FULLY IMPLEMENTED and actively used — keep this file

**1d. Delete Defunct Frontend Files:**
- Delete `frontend/src/controllers/` directory (12 controller files never imported)
- Delete `frontend/src/components/TaskBoard.ts`
- Delete `frontend/src/components/MessagePanel.ts`
- Delete `frontend/src/components/CalendarSyncPanel.ts` Done upto here
- Delete `frontend/src/services/AuthGateway.ts`
- Delete `frontend/src/services/NotificationSocketService.ts`
- Delete `frontend/src/composables/useAuth.ts`
- Remove imports of `useAuth` from `frontend/src/views/{GoogleLoginView,MicrosoftLoginView,HomeView,LoginView}.vue`

**1e. Fix Security Configuration:**
- In `backend/chore_sync/settings.py` line 154, change `DEFAULT_PERMISSION_CLASSES` from `AllowAny` to `IsAuthenticated`. Explicitly add `permission_classes = [AllowAny]` only to signup, login, verify-email, forgot-password, and reset-password views.
- Change `CORS_ALLOW_ALL_ORIGINS = True` (line 143) to `False` and enumerate allowed origins in `CORS_ALLOWED_ORIGINS`.

**1f. Add Django Channels (WebSocket Support):**
- Add `django-channels` and `daphne` to `pyproject.toml`. Update `settings.py` `INSTALLED_APPS` to include `'channels'` and set `ASGI_APPLICATION = 'chore_sync.asgi.application'`.
- Update `backend/chore_sync/asgi.py` to use `ProtocolTypeRouter` with HTTP (existing Django app) and WebSocket (new `ChoreConsumer`).

**1g. Create DRF Routers (Replacements for Deleted FastAPI Files):**
- Create new DRF-based endpoints for tasks and groups in Steps 4-6 (do NOT recreate the FastAPI files)

---

### Step 2: Fix Data Model Gaps ✅ COMPLETE

**File:** `backend/chore_sync/models.py`

**Actions — add the following fields/models:**

**2a. TaskOccurrence** — extend the existing model (lines 270–294):
- Replace `completed = BooleanField` with `status = CharField(choices=[pending, in_progress, snoozed, completed, overdue, reassigned])`
- Add `snooze_until = DateTimeField(null=True, blank=True)`
- Add `snooze_count = PositiveIntegerField(default=0)` (enforce max 2)
- Add `original_assignee = ForeignKey(User, null=True, related_name='originally_assigned')`
- Add `reassignment_reason = CharField(choices=[swap, emergency, system_rebalance], null=True)`
- Add `points_earned = PositiveIntegerField(null=True, blank=True)`
- Add `photo_proof = ImageField(upload_to='proof/', null=True, blank=True)`

**2b. Group** — extend (lines 127–162):
- Add `fairness_algorithm = CharField(choices=[time_based, count_based, difficulty_based, weighted], default='count_based')`
- Add `photo_proof_required = BooleanField(default=False)`
- Add `task_proposal_voting_required = BooleanField(default=False)`

**2c. TaskTemplate** — extend (lines 190–267):
- Expand `recurring_choice` choices to include: `weekly`, `monthly`, `custom` (currently only `none` and `every_n_days`)
- Add `days_of_week = JSONField(null=True)` (e.g., `["mon", "wed", "fri"]`)
- Add `difficulty = PositiveIntegerField(default=1)` (1–5 scale)
- Add `estimated_minutes = PositiveIntegerField(default=30)` (rename/supplement `estimated_hours`)
- Add `category = CharField(choices=[cleaning, cooking, maintenance, other], default='other')`

**2d. New model: UserStats**
```python
class UserStats(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stats')
    household = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='member_stats')
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    total_tasks_completed = models.PositiveIntegerField(default=0)
    total_points = models.PositiveIntegerField(default=0)
    tasks_completed_this_week = models.PositiveIntegerField(default=0)
    tasks_completed_this_month = models.PositiveIntegerField(default=0)
    on_time_completion_rate = models.FloatField(default=0.0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'household')
```

**2e. New model: Badge**
```python
class Badge(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=255, blank=True)
    criteria = models.JSONField(help_text="e.g. {'streak_days': 30} or {'tasks_completed': 100}")
    points_value = models.PositiveIntegerField(default=0)
```

**2f. New model: UserBadge**
```python
class UserBadge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    household = models.ForeignKey(Group, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge', 'household')
```

**2g. Notification** — extend (lines 902–969):
- Add `title = CharField(max_length=255, blank=True)`
- Add `action_url = CharField(max_length=512, null=True)`
- Add `sent_at = DateTimeField(null=True)`
- Expand `TYPE_CHOICES` to add: `deadline_reminder`, `emergency_reassign`, `badge_earned`, `marketplace_claim`

**2h. TaskSwap** — extend (lines 661–727):
- Add `expires_at = DateTimeField()` (48-hour window)
- Add `swap_type = CharField(choices=[direct_swap, open_request])` — currently the model is open-ended but the plan has two modes
- For 1:1 swaps, add `counterpart_task = FK(TaskOccurrence, null=True)` for the task being offered in return

After all model changes, run:
```bash
python manage.py makemigrations && python manage.py migrate
```

---

### Step 3: OAuth Token Encryption ✅ COMPLETE

**File:** `backend/chore_sync/models.py` line 321

**Actions:**
1. Install `django-fernet-fields` or `cryptography` library.
2. Replace `secret = models.JSONField(...)` with an encrypted field wrapper. The standard approach is to use `django-fernet-fields`'s `EncryptedTextField` storing the JSON as a string, or implement a custom `EncryptedJSONField` using Fernet symmetric encryption keyed off a dedicated `FIELD_ENCRYPTION_KEY` env var (not `SECRET_KEY`).
3. Write a data migration to re-encrypt existing records.

---

### Step 4: Implement Group Management Service + API ✅ COMPLETE

**Files:** `backend/chore_sync/services/group_service.py`, `backend/chore_sync/api/group_router.py`, `backend/chore_sync/urls.py`

**Actions (implement in `GroupOrchestrator`):**

`create_group(owner_id, name, reassignment_rule)`:
- Validate name length
- `Group.objects.create(...)` with `group_code = secrets.token_urlsafe(6).upper()`
- Create `GroupMembership(user=owner, group=group, role='moderator')`
- Create `GroupCalendar` settings record
- Return group data dict

`invite_member(group_id, email)`:
- Check requestor is moderator of group
- If user with email exists: create `GroupMembership` + send `Notification`
- If not: send invitation email with group_code for self-join

`generate_invite_code(group_id)`:
- Regenerate `group_code` on the `Group` and save

`compute_assignment_matrix(group_id)`:
- Query `UserStats` per member
- Return dict keyed by user_id with fairness scores based on `group.fairness_algorithm`

In `group_router.py` (now DRF), wire endpoints:
- `POST /api/groups/` → `create_group`
- `GET /api/groups/` → list user's groups via `GroupMembership`
- `GET /api/groups/{id}/` → group detail
- `POST /api/groups/{id}/invite/` → `invite_member`
- `GET /api/groups/{id}/members/` → list members with stats
- `GET /api/groups/{id}/assignment-matrix/` → `compute_assignment_matrix`
- `PATCH /api/groups/{id}/settings/` → update fairness algorithm, photo proof setting

Register all in `backend/chore_sync/urls.py`.

---

### Step 5: Implement Task Template Service + API ✅ COMPLETE

**Files:** `backend/chore_sync/services/task_template_service.py`, new `backend/chore_sync/api/task_template_router.py`, `backend/chore_sync/urls.py`

**Actions:**

`create_template(creator_id, group_id, payload)`:
- Validate: creator is member of group
- `TaskTemplate.objects.create(**payload, creator_id=creator_id, group_id=group_id)`
- Return serialized template

`list_templates(group_id)`:
- Return `TaskTemplate.objects.filter(group_id=group_id, active=True)`

`update_template(template_id, actor_id, updates)`:
- Validate: actor is member of template's group
- Patch allowed fields: name, details, recurrence, difficulty, estimated_minutes, category
- Save

`delete_template(template_id, actor_id)`:
- Set `active = False` (soft delete)
- Cancel future `TaskOccurrence` records with `status='pending'`

Endpoints:
- `GET/POST /api/groups/{id}/task-templates/`
- `GET/PATCH/DELETE /api/task-templates/{id}/`

---

### Step 6: Implement TaskOccurrence + Assignment Logic ✅ COMPLETE — commit `f1c7dc0`

**Files:** `backend/chore_sync/services/task_service.py`, `backend/chore_sync/services/task_lifecycle_service.py`, `backend/chore_sync/api/task_router.py`

**Actions:**

`generate_recurring_instances(task_template_id, horizon_days=7)`:
- Load `TaskTemplate`
- Compute dates by expanding recurrence pattern from `next_due` forward to `now + horizon_days`
- For each date: `TaskOccurrence.objects.get_or_create(template=t, deadline=date)` (the `unique_together` constraint prevents duplicates)
- For each newly created occurrence: call `assign_occurrence(occurrence)`

`assign_occurrence(occurrence)`:

Assignment uses a 3-stage scoring pipeline. Lower score = higher assignment priority.

**Stage 1 — Fairness score (via `GroupOrchestrator.compute_assignment_matrix`)**
- Returns a 0–1 normalised dict keyed by user_id (min-max normalisation across the group)
- Algorithm selected by `group.fairness_algorithm`:
  - **count_based**: score = `UserStats.total_tasks_completed`
  - **time_based**: score = `-(timezone.now() - last_occurrence.deadline).days` (negative days since last assignment — longer ago = lower raw score = higher priority after normalisation)
  - **difficulty_based**: score = `UserStats.total_points`
  - **weighted**: score = `(total_tasks_completed × 0.6) + (total_points × 0.4)`
- All four raw scores are min-max normalised to 0–1 before use

**Stage 2 — Preference multiplier (percentage-based, not fixed offset)**
- Fetch `TaskPreference` for each user against this template
- Multiply normalised score by preference weight:
  - `prefer` → `× 0.8` (20% reduction — nudges toward assignment without overriding fairness)
  - `neutral` → `× 1.0` (no change)
  - `avoid` → `× 1.2` (20% increase — nudges away proportionally)
- Percentage-based ensures a heavily overloaded user who "prefers" a task cannot jump the queue over a lightly loaded neutral user

**Stage 3 — Calendar availability penalty**
- Query `Event.objects.filter(calendar__user=user, blocks_availability=True, start__lt=deadline, end__gt=deadline, calendar__include_in_availability=True)`
- If conflict exists: add `+0.5` penalty to score (pushes them to back of queue)
- Do NOT exclude users — if everyone has a conflict the task still gets assigned to the fairest busy person

**Final assignment**
- `winner = min(scores, key=scores.get)`
- `occurrence.assigned_to = winner; occurrence.status = 'pending'; occurrence.save()`
- `Notification.objects.create(type='task_assigned', recipient=winner, task_occurrence=occurrence)`

`toggle_occurrence_completed(occurrence_id, completed, actor_id)`:
- Validate: actor is the assigned user (or a group moderator)
- If `completed=True`: set `status='completed'`, `completed_at=now`, calculate `points_earned = difficulty * 10`
- Update `UserStats`: increment `total_tasks_completed`, `total_points`, check streak
- If task had `photo_proof_required=True` on template and no photo uploaded: raise validation error
- Trigger badge evaluation (see Step 9)

Endpoints to wire in `task_router.py` (DRF):
- `GET /api/users/me/tasks/` → `list_user_tasks`
- `GET /api/groups/{id}/tasks/`
- `POST /api/task-templates/{id}/generate-occurrences/`
- `PATCH /api/tasks/{id}/` → update status, assignment
- `POST /api/tasks/{id}/complete/` → `toggle_occurrence_completed`
- `POST /api/tasks/{id}/snooze/` → (Step 8)
- `POST /api/tasks/{id}/emergency-reassign/` → (Step 8)

---

### Step 7: Celery Periodic Tasks ✅ COMPLETE — commit `f1c7dc0`

**File:** `backend/chore_sync/tasks.py`, `backend/chore_sync/settings.py`

**Actions — add these Celery tasks:**

`generate_daily_occurrences()` — schedule: daily at midnight
- For every active `TaskTemplate` across all groups: call `generate_recurring_instances(template_id, horizon_days=7)`

`dispatch_deadline_reminders()` — schedule: every 15 minutes
- Query `TaskOccurrence.objects.filter(status__in=['pending','snoozed'], deadline__lte=now+24h, deadline__gt=now)`
- For each, check if reminder already sent (add `reminder_sent_at` field to TaskOccurrence or use a separate `ReminderLog` table)
- If not sent: create `Notification(type='deadline_reminder', recipient=occurrence.assigned_to)`

`mark_overdue_tasks()` — schedule: every 15 minutes
- Query `TaskOccurrence.objects.filter(status='pending', deadline__lt=now)`
- Set `status='overdue'`; notify assignee

`cleanup_expired_swaps()` — schedule: daily
- Delete `TaskSwap.objects.filter(status='pending', expires_at__lt=now)`

`recalculate_leaderboard()` — schedule: hourly
- Recalculate `UserStats` per household from `TaskOccurrence` aggregates

`evaluate_badges(user_id, group_id)` — schedule: on-demand (called after task completion)
- Load all `Badge` records; evaluate `criteria` JSON against current `UserStats`; award any not yet in `UserBadge`

Configure in `settings.py`:
```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'generate-daily-occurrences': {
        'task': 'chore_sync.tasks.generate_daily_occurrences',
        'schedule': crontab(hour=0, minute=0),
    },
    'dispatch-deadline-reminders': {
        'task': 'chore_sync.tasks.dispatch_deadline_reminders',
        'schedule': 900,  # every 15 minutes
    },
    'mark-overdue-tasks': {
        'task': 'chore_sync.tasks.mark_overdue_tasks',
        'schedule': 900,
    },
    'cleanup-expired-swaps': {
        'task': 'chore_sync.tasks.cleanup_expired_swaps',
        'schedule': crontab(hour=2, minute=0),
    },
    'recalculate-leaderboard': {
        'task': 'chore_sync.tasks.recalculate_leaderboard',
        'schedule': 3600,  # every hour
    },
}
```

---

### Step 8: Task Lifecycle Features (Snooze, Swap, Emergency Reassign) ✅ COMPLETE

**File:** `backend/chore_sync/services/task_lifecycle_service.py`

**Snooze (`snooze_task(occurrence_id, snooze_until, actor_id)`):**
- Validate `snooze_count < 2` and `snooze_until <= occurrence.deadline + 24h`
- Set `status='snoozed'`, `snooze_until=snooze_until`, increment `snooze_count`
- Save; re-schedule reminder

**Task Swap (`create_swap_request(task_id, from_user_id, reason, to_user_id=None)`):**
- Validate from_user is assignee
- `TaskSwap.objects.create(task=occurrence, from_user=from_user, to_user=to_user, expires_at=now+48h)`
- If `to_user` specified: notify them directly. If None: notify all group members

`respond_to_swap_request(swap_id, accept, actor_id)`:
- If accept: set `occurrence.assigned_to = actor_id`, `swap.status='accepted'`, `swap.decided_at=now`
- Notify original assignee of outcome

**Emergency Reassign (`emergency_reassign(occurrence_id, actor_id, reason)`):**
- Validate actor is assignee
- Check monthly limit: `TaskOccurrence.objects.filter(original_assignee=actor, reassignment_reason='emergency', deadline__month=now.month).count() < 3`
- Set `original_assignee=actor`, `reassignment_reason='emergency'`, `assigned_to=None` (open)
- Broadcast `Notification(type='emergency_reassign')` to all group members
- First member to call `accept_emergency(occurrence_id, actor_id)` gets assigned

---

### Step 9: Gamification (Streaks, Points, Badges, Leaderboard) ✅ COMPLETE

**Files:** new `backend/chore_sync/services/gamification_service.py`, `backend/chore_sync/models.py`

**Streak Logic (`update_streak(user_id, group_id)`):**
- Called after every task completion
- If `user.last_streak_date == yesterday`: increment `on_time_streak_days`; update `longest_on_time_streak_days` if needed
- Else if `user.last_streak_date != today`: reset `on_time_streak_days = 1`
- Update `user.last_streak_date = today`
- Update `UserStats` record

**Points Logic:**
- Base points = `difficulty * 10`
- On-time bonus: +20% if `completed_at < deadline`
- Emergency help bonus: +20% if `reassignment_reason='emergency'` and actor is the helper
- Snooze penalty: -10% per snooze used

**Badge Evaluation:**
- Criteria examples stored in `Badge.criteria` JSONField:
  - `{"streak_days": 7}` → check `UserStats.current_streak >= 7`
  - `{"tasks_completed": 50}` → check `UserStats.total_tasks_completed >= 50`
  - `{"category_count": {"category": "cooking", "count": 50}}`
- Award with `UserBadge.objects.get_or_create(user, badge, household)`
- Send `Notification(type='badge_earned')` on new award

**Leaderboard API endpoint:**
- `GET /api/groups/{id}/leaderboard/`
- Query `UserStats.objects.filter(household_id=id).order_by('-total_points')`
- Return list: rank, username, total_points, current_streak, on_time_completion_rate

---

### Step 10: Notification Delivery + WebSocket Integration ✅ COMPLETE

**Files:** `backend/chore_sync/services/notification_service.py`, new `backend/chore_sync/consumers.py`, `backend/chore_sync/asgi.py`

**Actions:**

`emit_notification(recipient_id, type, content, **fk_references)`:
- `Notification.objects.create(recipient_id=recipient_id, type=type, content=content, ...fks)`
- Call `fan_out_realtime(recipient_id, notification.id)`

`fan_out_realtime(recipient_id, notification_id)`:
- Use `channels.layers.get_channel_layer()` to `async_to_sync(layer.group_send)('user_{recipient_id}', {...})`

Create `consumers.py` with `ChoreConsumer(AsyncWebsocketConsumer)`:
- `connect`: authenticate from session, add to `user_{user.id}` and `household_{group_id}` groups
- `disconnect`: remove from groups
- `receive`: handle incoming messages (chat messages, swap responses)
- `notification_message` handler: serialize and send to WebSocket client

Update `asgi.py`:
```python
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from chore_sync.consumers import ChoreConsumer

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter([
            path('ws/chores/', ChoreConsumer.as_asgi()),
        ])
    ),
})
```

---

### Step 11: Group Proposal / Voting Endpoints ✅ COMPLETE

**File:** `backend/chore_sync/services/proposal_service.py`, new `backend/chore_sync/api/proposal_router.py`

**Actions:**

`create_proposal(proposer_id, group_id, task_template_id, reason)`:
- Validate proposer is group member
- `TaskProposal.objects.create(...)` with `voting_deadline = now + 72h`
- Notify all group members

`cast_vote(proposal_id, voter_id, choice)`:
- `TaskVote.objects.update_or_create(proposal=p, voter=voter, defaults={'choice': choice})`
- After vote: check if all members have voted or deadline has passed
- Calculate `support_ratio = support_votes / (support + reject votes)` (excluding abstain)
- If `support_ratio >= proposal.required_support_ratio`: set `state='approved'`, activate the `TaskTemplate`

Endpoints:
- `POST /api/groups/{id}/proposals/`
- `GET /api/groups/{id}/proposals/`
- `POST /api/proposals/{id}/vote/`

---

### Step 12: Stats Dashboard Endpoints ✅ COMPLETE

**Files:** new `backend/chore_sync/api/stats_router.py`, `backend/chore_sync/services/insights_service.py`

**Endpoints:**
- `GET /api/users/me/stats/` — return `UserStats` for the requesting user across all households
- `GET /api/users/me/badges/` — return `UserBadge.objects.filter(user=request.user).select_related('badge')`
- `GET /api/groups/{id}/stats/` — household-level aggregates: total tasks, completion rate, most-completed task, fairness distribution

---

### Step 13a: Frontend Wiring — Controllers & Infrastructure ✅ COMPLETE

**Files:** `frontend/src/controllers/`, `frontend/src/services/api.ts`

**Actions:**
1. ✅ Implement `GroupDetailController.ts` — calls `GET /api/groups/{id}/`, `GET /api/groups/{id}/tasks/`, `GET /api/groups/{id}/members/`
2. ✅ Implement `MyTasksController.ts` — calls `GET /api/users/me/tasks/`; exposes snooze/complete/swap actions
3. ✅ Wire `NotificationSocketService.ts` to the new Django Channels WebSocket endpoint
4. ✅ Update Pinia `auth.ts` store to store `user_id` and `household_ids`
5. ✅ Add PWA manifest: `frontend/public/manifest.json` with app name, icons, `display: standalone`
6. ✅ Extend `api.ts` with `groupApi`, `taskApi`, `notificationApi`, `statsApi`
7. ✅ Bootstrap populates `userId` + `householdIds` from profile + groups on login

---

### Step 13b: Frontend Views — Core UI ✅ COMPLETE

**New routes and views required:**

#### New Routes
- `/groups` → `GroupsView.vue` — list all groups, create group
- `/groups/:id` → `GroupDetailView.vue` — tabbed group hub
- `/tasks` → `MyTasksView.vue` — personal task board

#### `GroupsView.vue` (`/groups`)
- List all groups the user belongs to (call `groupApi.list()`)
- Show group name, code, role, fairness algorithm
- "Create group" button → inline form: name, fairness algorithm, reassignment rule
- Clicking a group navigates to `/groups/:id`
- Redirect `/` (HomeView) to `/groups` after login

#### `GroupDetailView.vue` (`/groups/:id`)
Tabbed layout with the following tabs:

| Tab | Content | API calls |
|---|---|---|
| Tasks | Task list with complete/snooze/swap actions | `GET /api/groups/{id}/tasks/` |
| Members | Member list with stats | `GET /api/groups/{id}/members/` |
| Leaderboard | Ranked points table | `GET /api/groups/{id}/leaderboard/` |
| Proposals | List proposals, create proposal, vote | `GET/POST /api/groups/{id}/proposals/`, `POST /api/proposals/{id}/vote/` |
| Chat | Message thread, send message via WebSocket | `NotificationSocketService.sendChatMessage()` |
| Templates | List/create task templates | `GET/POST /api/groups/{id}/task-templates/` |
| Settings | Fairness algo, photo proof, voting toggle (moderator only) | `PATCH /api/groups/{id}/settings/` |

#### `MyTasksView.vue` (`/tasks`)
- List all tasks across all groups (call `taskApi.myTasks()`)
- Filter by status (pending / snoozed / overdue / completed)
- Per task: template name, group, deadline, status badge, points
- Actions: Complete button, Snooze (date picker), Request Swap (user picker)
- Emergency reassign button (if applicable)

#### Notification bell (App.vue navbar)
- Bell icon with unread count badge
- Click opens slide-out drawer
- Drawer lists active notifications (call `notificationApi.list()`)
- Per notification: mark read, dismiss
- `NotificationSocketService` pushes new ones in real time

#### Profile page additions (`UpdateProfileView.vue`)
- Add stats section: total tasks, points, streak, on-time rate (call `statsApi.myStats()`)
- Add badges section: grid of earned badges (call `statsApi.myBadges()`)

---

### Step 14: Outlook Calendar Sync ✅ COMPLETE (Graph webhook subscriptions pending — see Step 18)

**Files:** `backend/chore_sync/sync_providers/outlook_provider.py`, new `backend/chore_sync/api/outlook_calendar_router.py`, `backend/chore_sync/urls.py`, `frontend/src/services/calendarService.ts`, new `frontend/src/views/OutlookCalendarSelectView.vue`

**Context:** Microsoft *login* is fully implemented (MSAL on frontend, JWT validation against Azure AD JWKS on backend, credentials stored encrypted in `ExternalCredential`). What's missing is the calendar sync itself — reading and writing events from Outlook/Microsoft Graph.

**Backend — implement `OutlookCalendarProvider` (`sync_providers/outlook_provider.py`):**

All 4 methods currently raise `NotImplementedError`. Implement using Microsoft Graph API (`https://graph.microsoft.com/v1.0`) with a bearer token retrieved from `ExternalCredential.secret` for the user:

`list_calendars(user_id)`:
- Load `ExternalCredential(user_id=user_id, provider='microsoft')` and decrypt `secret` to get access token
- `GET https://graph.microsoft.com/v1.0/me/calendars` with `Authorization: Bearer <token>`
- Handle pagination via `@odata.nextLink`
- Return normalised list: `[{'id': ..., 'name': ..., 'is_primary': ...}]`

`pull_events(user_id, delta_link=None)`:
- If `delta_link` provided: `GET <delta_link>` (incremental sync)
- Else: `GET /me/events/delta?$select=subject,start,end,isCancelled` (full sync)
- Follow `@odata.nextLink` until exhausted; capture final `@odata.deltaLink` and persist on `ExternalCredential` or a separate `SyncState` record
- Normalise events to match internal `Event` schema; detect deletions via `@removed` annotation
- Return `{'events': [...], 'delta_link': '...'}`

`push_events(user_id, event_payloads)`:
- For each payload: `POST /me/events` (create) or `PATCH /me/events/{id}` (update) or `DELETE /me/events/{id}`
- Handle Graph throttling: respect `Retry-After` header on 429 responses
- Map response `id` back to local event and persist as `external_id` on the `Event` model

`renew_subscription(user_id)`:
- `POST /subscriptions` to create a Graph webhook if none exists, or `PATCH /subscriptions/{id}` to extend expiry (max 3 days for calendar subscriptions)
- Persist subscription ID and expiry on `ExternalCredential.secret` or a `SyncState` record
- Called by a Celery periodic task (add to Step 7's `CELERY_BEAT_SCHEDULE`)

**Backend — API endpoints (new `outlook_calendar_router.py`):**
- `GET /api/calendar/outlook/auth-url/` → return Microsoft OAuth URL (use MSAL config from settings)
- `GET /api/calendar/outlook/calendars/` → call `list_calendars(request.user.id)`
- `POST /api/calendar/outlook/select/` → persist selected calendar IDs on `ExternalCredential.secret`
- `POST /api/calendar/outlook/sync/` → call `pull_events` + `push_events`; return summary

Register all in `urls.py`.

**Required settings** (`secrets.env` + `settings.py`):
```
MSAL_CLIENT_ID=<same as VITE_MSAL_CLIENT_ID>
MSAL_CLIENT_SECRET=<Azure AD client secret>
MSAL_AUTHORITY=https://login.microsoftonline.com/common
```

**Frontend — `calendarService.ts`:** add:
```ts
getOutlookAuthUrl()    → GET /api/calendar/outlook/auth-url/
listOutlookCalendars() → GET /api/calendar/outlook/calendars/
selectOutlookCalendars(ids: string[]) → POST /api/calendar/outlook/select/
syncOutlook()          → POST /api/calendar/outlook/sync/
```

**Frontend — new `OutlookCalendarSelectView.vue`:**
- Mirror `GoogleCalendarSelectView.vue` but call `calendarService.listOutlookCalendars()` / `calendarService.selectOutlookCalendars()`
- Add route: `{ path: '/calendar/outlook/select', name: 'outlook-calendar-select', component: OutlookCalendarSelectView }`

**Token refresh:** Microsoft access tokens expire in 1 hour. Before any Graph call, check expiry on the stored credential and call `POST /oauth2/v2.0/token` with the refresh token if needed. Update `ExternalCredential.secret` with the new token pair.

---

### Step 15: Dark Mode ✅ COMPLETE

**Files:** `frontend/src/main.ts`, `frontend/src/App.vue`, `frontend/src/quasar-variables.sass`

**Actions:**
1. Enable Quasar dark plugin in `main.ts`: `app.use(Quasar, { plugins: { Dark } })`
2. Add a dark mode toggle button in `App.vue` toolbar: `$q.dark.toggle()`
3. Persist the user's preference to `localStorage` and restore it on app startup via `$q.dark.set(stored)`
4. Add dark-mode overrides to `quasar-variables.sass` for any custom colours that don't invert correctly with Quasar's defaults
5. Test all 12 views in dark mode for readability

---

### Step 16: *(moved — see Step 25: Security Hardening)*

---

### Step 17: Calendar Architecture Refactor, Logical Bug Fixes & Improvements ✅ COMPLETE

This step consolidates all calendar-related architectural decisions, bug fixes, and behavioural improvements identified during design review. Must be completed before Step 14 (Outlook Calendar Sync).

---

#### 17a. Calendar Model Refactor (Option A — provider-specific detail models)

**Problem:** `Calendar` model is tightly coupled to Google-specific fields. Adding Outlook support would pollute it further with nullable Outlook-only columns.

**Model changes (1 migration):**

`Calendar` — remove Google-specific fields, clarify sync intent:
- Drop `back_sync_enabled` — dead field, never set or read anywhere
- Drop `sync_enabled` — redundant once webhooks are live; replaced by watch channel liveness on `GoogleCalendarSync`. Retain only as `paused` flag on the provider-specific model for admin kill-switch
- Rename `writable` → `push_enabled` — reflects user intent (push app events out) rather than OAuth access level
- Add `is_task_writeback = BooleanField(default=False)` — exactly one calendar per user receives task assignment events. Enforced in save logic (setting True clears all others for that user).

New model `GoogleCalendarSync` (OneToOne → `Calendar`, `related_name='google_sync'`):
```python
class GoogleCalendarSync(models.Model):
    calendar       = models.OneToOneField(Calendar, on_delete=models.CASCADE, related_name='google_sync')
    sync_token     = models.CharField(max_length=512, null=True, blank=True)   # incremental sync token
    checkpoint_date = models.DateTimeField(null=True, blank=True)              # resume point for interrupted initial sync
    active_task_id = models.CharField(max_length=255, null=True, blank=True)   # Celery task ID — deduplication
    channel_id     = models.CharField(max_length=255, null=True, blank=True)   # Google Watch channel ID
    resource_id    = models.CharField(max_length=255, null=True, blank=True)   # Google Watch resource ID
    watch_expires_at = models.DateTimeField(null=True, blank=True)             # watch channel expiry
    webhook_token  = models.CharField(max_length=255, null=True, blank=True)   # verification token sent with webhook
    paused         = models.BooleanField(default=False)                        # admin kill-switch (replaces sync_enabled)
    oauth_writable = models.BooleanField(default=False)                        # reflects Google accessRole (owner/writer)
```

New stub model `OutlookCalendarSync` (OneToOne → `Calendar`, `related_name='outlook_sync'`) — ready for Step 14:
```python
class OutlookCalendarSync(models.Model):
    calendar               = models.OneToOneField(Calendar, on_delete=models.CASCADE, related_name='outlook_sync')
    delta_link             = models.TextField(null=True, blank=True)
    subscription_id        = models.CharField(max_length=255, null=True, blank=True)
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
```

Migrate all `google_calendar_service.py` references from `calendar.sync_token`, `calendar.channel_id` etc. to `calendar.google_sync.sync_token`, `calendar.google_sync.channel_id` etc.

Update `admin.py` — `GoogleCalendarSync` inline on `CalendarAdmin`, remove dead fields from list_display/list_filter.

---

#### 17b. CalendarProvider Abstraction

**Problem:** task lifecycle code would need to import `GoogleCalendarService` directly, making Outlook support require changes throughout.

**New file `sync_providers/base.py`:**
```python
from abc import ABC, abstractmethod

class CalendarProvider(ABC):
    @abstractmethod
    def push_event(self, calendar: Calendar, event: Event) -> str: ...      # returns external_event_id
    @abstractmethod
    def update_event(self, calendar: Calendar, event: Event) -> str: ...
    @abstractmethod
    def delete_event(self, calendar: Calendar, external_event_id: str) -> None: ...
    @abstractmethod
    def pull_events(self, calendar: Calendar) -> int: ...                   # returns count of events synced
```

**Dispatcher `sync_providers/registry.py`:**
```python
def get_provider(calendar: Calendar) -> CalendarProvider:
    if calendar.provider == 'google':
        return GoogleProvider(calendar.credential)
    if calendar.provider == 'microsoft':
        return OutlookProvider(calendar.credential)
    raise ValueError(f"No provider for: {calendar.provider}")
```

Migrate `GoogleCalendarService.push_created_event`, `push_updated_event`, push deletion logic into `sync_providers/google_provider.py` implementing `CalendarProvider`. `GoogleCalendarService` retains OAuth, sync, and watch channel management — only event push/delete moves to the provider class.

---

#### 17c. Task Writeback

**Problem:** assigning a task to a user never creates a calendar event. Reassignment never cleans up the old event. The `is_task_writeback` flag (17a) and `CalendarProvider` abstraction (17b) must exist first.

**Behaviour:**

On task assign (`task_lifecycle_service.py` — `assign_occurrence`):
- Find assignee's `Calendar` where `is_task_writeback=True`
- If found: create `Event(source='task', task_occurrence=occurrence, calendar=cal, ...)`
- If calendar has `push_enabled=True`: `get_provider(cal).push_event(cal, event)`

On reassignment (swap accepted, emergency accepted, system rebalance):
- Find old assignee's `Event` linked to this `TaskOccurrence` via `task_occurrence` FK
- If it has `external_event_id` and calendar has `push_enabled`: `get_provider(cal).delete_event(cal, event.external_event_id)`
- Delete the `Event` record
- Run assign flow above for new assignee

On task complete/cancel:
- `get_provider(cal).update_event(cal, event)` — updates title/description to reflect new status

**Frontend — `GoogleCalendarSelectView.vue`:**
- Replace per-calendar "Allow writeback" toggle with a **radio group** — user picks one calendar as task writeback target or selects "None"
- Label: "Receive task events"
- Saves `is_task_writeback=True` on selected calendar, `False` on all others for that user

---

#### 17d. Async Initial Google Calendar Sync

**Problem:** `GoogleCalendarSyncAPIView.post` runs `sync_events()` synchronously on the request thread. Large calendars time out. No progress feedback to the user.

**Fix:**

`GoogleCalendarSyncAPIView.post`:
- Check `GoogleCalendarSync.active_task_id` — if set, revoke old task, clear field
- Queue `initial_google_sync_task.delay(user_id)`, store returned task ID on `google_sync.active_task_id`
- Return `202 Accepted { "detail": "Sync started. You'll be notified when complete." }`

`initial_google_sync_task(user_id)` — on-demand Celery task on `calendar_sync` queue:
1. Load `GoogleCalendarSync.checkpoint_date` — if set, resume from there; else start from 2 years ago
2. Process events in **monthly chunks** using `timeMin`/`timeMax` params
3. After each chunk: save `checkpoint_date = chunk_end` to DB (crash-safe resume point)
4. Refresh OAuth token **before each chunk** (tokens expire after 1 hour — long syncs outlast them)
5. On `429`/`403 rateLimitExceeded`: save checkpoint, `raise self.retry(countdown=120 * 2**retries, max_retries=8)` — exponential backoff up to ~8 hours, covering daily quota reset
6. On completion: save final `sync_token`, clear `checkpoint_date`, clear `active_task_id`
7. **Register watch channel here** (not in `GoogleCalendarSelectAPIView`) — only after `sync_token` is saved
8. `emit_notification(user_id, notification_type='calendar_sync_complete', title='Google Calendar synced', content='Your calendars are ready.', action_url='/calendar')`

Remove `ensure_watch_channel()` call from `GoogleCalendarSelectAPIView` — watch registration now belongs to step 7 above.

**Worker startup:**
```bash
# Dedicated calendar sync worker — max 3 concurrent syncs
celery -A chore_sync worker -Q calendar_sync --concurrency=3 -l info

# Default worker for all other tasks
celery -A chore_sync worker -Q default --concurrency=4 -l info
```

---

#### 17e. Google Calendar Beat Jobs

**Two new periodic tasks** added to `CELERY_BEAT_SCHEDULE`, both on `calendar_sync` queue:

`renew_google_watch_channels()` — daily at 3am:
- Query `GoogleCalendarSync.objects.filter(watch_expires_at__lt=now + timedelta(days=2), paused=False)`
- For each: call `ensure_watch_channel(cal)` to renew
- Lightweight — one API call per calendar per week under normal conditions

`catchup_google_calendar_sync()` — every 6 hours:
- Query `GoogleCalendarSync.objects.filter(watch_expires_at__lt=now, paused=False)`
- For each: run full `sync_events(cal)`, then re-register watch channel
- Under healthy webhook conditions this queryset is always empty — zero cost

```python
CELERY_BEAT_SCHEDULE = {
    # ... existing jobs ...
    'renew-google-watch-channels': {
        'task': 'chore_sync.tasks.renew_google_watch_channels',
        'schedule': crontab(hour=3, minute=0),
    },
    'catchup-google-calendar-sync': {
        'task': 'chore_sync.tasks.catchup_google_calendar_sync',
        'schedule': crontab(minute=0, hour='*/6'),
    },
}
```

---

#### 17f. Google API Correctness Fixes

**`sync_token` 410 Gone handling:**
- `_sync_single_calendar` must catch `HttpError` with `status=410`
- On 410: clear `GoogleCalendarSync.sync_token`, re-run as full sync (no syncToken param), save fresh token on completion
- Currently unhandled — incremental sync silently fails if Google invalidates the token

**`maxResults=2500` on all `events().list()` calls:**
- Current default is 250 events per page — 10x more API calls than necessary
- Add `maxResults=2500` to every `events().list()` call in `_sync_single_calendar`
- Reduces quota consumption and initial sync time by up to 10x for large calendars

**Webhook signature validation:**
- Current webhook handler (`GoogleCalendarWebhookAPIView`) does not validate `X-Goog-Channel-Token`
- Anyone who discovers the webhook URL can POST fake payloads and trigger spurious syncs
- Fix: look up `GoogleCalendarSync` by `X-Goog-Channel-ID` header, compare `X-Goog-Channel-Token` against stored `webhook_token`, return `403` on mismatch
- Handle `X-Goog-Resource-State: sync` (initial verification ping) — respond `200` immediately, skip sync

**Race condition — watch channel registration timing:**
- Currently `ensure_watch_channel()` is called in `GoogleCalendarSelectAPIView` before initial sync runs
- If a Google event changes while initial sync is in progress, webhook fires incremental sync using a `sync_token` that doesn't exist yet → falls back to full sync → two concurrent full syncs on the same calendar
- Fix: move watch channel registration to end of `initial_google_sync_task` (already covered in 17d)

---

#### 17g. Notification Model & Deep Links

**Model change (1 migration):**
- `Notification.type`: remove `choices=TYPE_CHOICES` — plain `CharField(max_length=50)`. New notification types (e.g. `calendar_sync_complete`) never require a migration.
- `Notification.action_url`: change from `URLField` to `CharField(max_length=255)` — stores a relative frontend route path (e.g. `/tasks`, `/groups/abc-123`), not a full URL. Works regardless of domain/port.

**`emit_notification()` signature update:**
- Add `action_url: str = ''` parameter
- Pass to `Notification.objects.create`

**All existing `emit_notification()` call sites** — add `action_url`:

| Notification type | `action_url` |
|---|---|
| `task_assigned` | `/tasks` |
| `task_swap` | `/tasks` |
| `emergency_reassignment` | `/tasks` |
| `deadline_reminder` | `/tasks` |
| `group_invite` | `/groups/{group_id}` |
| `task_proposal` | `/groups/{group_id}` |
| `message` | `/groups/{group_id}` |
| `badge_earned` | `/profile` |
| `calendar_sync_complete` | `/calendar` |

**Frontend — `App.vue` notification drawer:**
- Make each notification `q-item` clickable
- Add `handleNotifClick(n)`:
  ```typescript
  function handleNotifClick(n: any) {
    if (n.action_url) router.push(n.action_url);
    if (!n.read) markRead(n.id);
    notifDrawer.value = false;
  }
  ```

---

## Implementation Priority Order

| Priority | Step | Rationale |
|---|---|---|
| P0 | Step 1 (Fix Architecture) | Nothing else can be wired until DRF is used consistently and permissions are fixed |
| P0 | Step 2 (Model gaps) + migrations | All subsequent steps depend on correct schema |
| P1 | Step 3 (Token encryption) | Security blocker before any more OAuth users |
| P1 | ~~Step 4 (Group API)~~ ✅ DONE | Required for all household features |
| P1 | ~~Step 5 (TaskTemplate API)~~ ✅ DONE | Required for task generation |
| P1 | Step 6 (TaskOccurrence + Assignment) | Core product value |
| P2 | Step 7 (Celery Jobs) | Automation of recurring tasks and reminders |
| P2 | Step 8 (Snooze/Swap/Emergency) | Phase 2 features |
| P2 | Step 10 (Notifications + WebSocket) | Real-time UX |
| P3 | Step 9 (Gamification) | Phase 3 |
| P3 | Step 11 (Proposals/Voting) | Phase 3–4 |
| P3 | Step 12 (Stats Dashboard) | Phase 4 |
| P4 | Step 13 (Frontend Wiring) | Follows backend completion |
| P4 | Step 14 (Outlook Calendar Sync) ✅ | Core sync done; webhook subscriptions in Step 18 |
| P4 | Step 15 (Dark Mode) ✅ | Complete |
| P2 | Step 17 (Calendar Architecture Refactor) ✅ | Complete |
| P2 | Step 18 (Outlook Graph Webhooks + writeback UI) | Real-time Outlook push; writeback toggle in frontend |
| P3 | Step 19 (Photo Proof upload) | ImageField exists; needs upload endpoint + UI enforcement |
| P3 | Step 20 (Task Marketplace) | Phase 4 feature from project plan |
| P3 | Step 21 (Smart Suggestions) | Pattern/availability/fairness suggestions via Celery daily job |
| P2 | Step 22 (Additional deadline reminders + badge criteria) | 3h/at-due reminders; Early Bird, Team Player, Negotiator badges |
| P3 | Step 23 (Stats visualizations) | Chart.js frontend components for leaderboard & stats |
| P4 | Step 24 (Notification preferences) | Per-user notification type config + quiet hours |
| P4 | Step 25 (Security Hardening) | Pre-production; includes SSE 403 fix |
| P3 | Step 26 (Fairness & calendar availability fixes) | time_based uses estimated_time; assignment checks calendar blocks |
| P3 | Step 27 (TaskAssignmentHistory model) | Full history log for every assignment/swap/emergency |
| P5 | Step 28 (PWA) | Mobile install prompt; service worker; offline support |

---

### Step 18: Outlook Calendar — Graph Webhook Subscriptions + Frontend Writeback Toggle

**Context:** Step 14 implemented delta-link sync and the `OutlookCalendarProvider` writeback. Two gaps remain:
1. No real-time push when the user's Outlook calendar changes (catchup task covers it every 6h but with lag)
2. The `OutlookCalendarSelectView.vue` frontend doesn't expose the `is_task_writeback` toggle — the API already handles it

**Backend — Graph webhook subscription (`renew_subscription`):**

`OutlookCalendarSync` already has `subscription_id` and `subscription_expires_at` fields.

In `OutlookCalendarService`:
```python
def renew_subscription(self, calendar: Calendar) -> None:
    """Create or extend a Graph change-notification subscription (max 3-day expiry)."""
    sync_state = OutlookCalendarSync.objects.get(calendar=calendar)
    expiry = timezone.now() + timedelta(days=3)
    payload = {
        "changeType": "created,updated,deleted",
        "notificationUrl": f"{settings.BACKEND_BASE_URL}/api/calendar/outlook/webhook/",
        "resource": f"/me/calendars/{calendar.external_id}/events",
        "expirationDateTime": expiry.isoformat(),
        "clientState": settings.OUTLOOK_WEBHOOK_SECRET,
    }
    if sync_state.subscription_id:
        # PATCH to extend
        requests.patch(f"{GRAPH_BASE}/subscriptions/{sync_state.subscription_id}",
                       json={"expirationDateTime": expiry.isoformat()}, headers=self._headers(), timeout=15)
    else:
        resp = requests.post(f"{GRAPH_BASE}/subscriptions", json=payload, headers=self._headers(), timeout=15)
        resp.raise_for_status()
        sync_state.subscription_id = resp.json()["id"]
    sync_state.subscription_expires_at = expiry
    sync_state.save(update_fields=["subscription_id", "subscription_expires_at"])
```

Add beat job in `tasks.py`:
```python
@shared_task
def renew_outlook_subscriptions():
    """Renew Graph subscriptions expiring within 1 hour. Runs every 2 hours."""
    ...
```

Add to `CELERY_BEAT_SCHEDULE` in `settings.py`:
```python
'renew-outlook-subscriptions': {'task': 'chore_sync.tasks.renew_outlook_subscriptions', 'schedule': 2 * 3600},
```

Add webhook receiver endpoint `OutlookCalendarWebhookAPIView` (POST, `AllowAny`, CSRF-exempt):
- Validate `clientState` header against `settings.OUTLOOK_WEBHOOK_SECRET`
- On validation ping (no body value): return 200
- On change notification: queue `initial_outlook_sync_task` for the affected calendar

Register in `urls.py`: `path('api/calendar/outlook/webhook/', OutlookCalendarWebhookAPIView.as_view())`

**Required settings:**
```
BACKEND_BASE_URL=http://localhost:8000  # must be publicly accessible for webhooks in production
OUTLOOK_WEBHOOK_SECRET=<random secret>
```

**Frontend — `OutlookCalendarSelectView.vue`:**
- Add a "Use for task events" toggle per calendar row (maps to `is_task_writeback`)
- Only one calendar can be selected as task writeback (radio-style: selecting one clears others)
- Pass `is_task_writeback` in the POST payload to `/api/calendar/outlook/select/`
- Show "Sync in progress…" banner when response contains non-empty `syncing` array

---

### Step 19: Photo Proof Upload

**Context:** `TaskOccurrence.photo_proof = ImageField(upload_to='proof/', blank=True)` exists. `TaskTemplate.photo_proof_required` exists. No upload endpoint or enforcement in the UI.

**Backend — upload endpoint:**

Add `POST /api/tasks/<pk>/upload-proof/` (`TaskPhotoProofAPIView`):
```python
class TaskPhotoProofAPIView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication]

    def post(self, request, pk):
        occurrence = get_object_or_404(TaskOccurrence, pk=pk, assigned_to=request.user)
        file = request.FILES.get('photo')
        if not file:
            return Response({'detail': 'No file provided.'}, status=400)
        # Validate: max 5 MB, image MIME types only
        if file.size > 5 * 1024 * 1024:
            return Response({'detail': 'File too large (max 5 MB).'}, status=400)
        if file.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
            return Response({'detail': 'Invalid file type.'}, status=400)
        occurrence.photo_proof = file
        occurrence.save(update_fields=['photo_proof'])
        return Response({'url': occurrence.photo_proof.url})
```

Register: `path('api/tasks/<uuid:pk>/upload-proof/', TaskPhotoProofAPIView.as_view())`

**Backend — enforce on complete:**
In `TaskLifecycleService.toggle_occurrence_completed`:
```python
if occurrence.template.photo_proof_required and not occurrence.photo_proof:
    raise ValueError("Photo proof required before marking this task complete.")
```

**Frontend — complete button in `MyTasksView.vue` / `GroupDetailView.vue`:**
- If `task.photo_proof_required` and no `task.photo_url`:
  - Show camera icon button → file input → POST to `/api/tasks/{id}/upload-proof/`
  - Only enable "Complete" button after upload succeeds
- Show uploaded photo thumbnail for completed tasks

---

### Step 20: Task Marketplace

**Context:** From project plan Phase 4. Users can list an assigned task on the marketplace with optional bonus points; any household member can claim it (first-come-first-served).

**Backend — new model `MarketplaceListing`:**
```python
class MarketplaceListing(models.Model):
    task_occurrence = models.OneToOneField(TaskOccurrence, on_delete=models.CASCADE, related_name='marketplace_listing')
    listed_by       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='marketplace_listings')
    group           = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='marketplace_listings')
    bonus_points    = models.PositiveIntegerField(default=0)
    expires_at      = models.DateTimeField()  # 24h after creation
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Cannot list tasks due in <2 hours
        ]
```

**Backend — service `MarketplaceService`:**
- `list_task(*, user, occurrence_id, bonus_points=0) -> MarketplaceListing`
  - Validates: task assigned to user, not due in <2 hours, not already listed
  - Creates listing with `expires_at = now() + 24h`
  - Broadcasts WebSocket notification to household: `"User X listed 'Task Y' on the marketplace"`
- `claim_task(*, user, listing_id) -> TaskOccurrence`
  - Validates: listing not expired, user is household member, user is not the lister
  - Reassigns `occurrence.assigned_to` to claimer
  - Awards `bonus_points` to claimer
  - Deletes listing
  - Notifies both parties

**Backend — beat job:** `cleanup_expired_marketplace_listings` — hourly, deletes expired listings and returns tasks to original assignee.

**Backend — endpoints:**
- `POST /api/tasks/<pk>/list-marketplace/` — list task (body: `{bonus_points: int}`)
- `GET /api/groups/<pk>/marketplace/` — list active listings for household
- `POST /api/marketplace/<pk>/claim/` — claim a listing

**Frontend — `GroupDetailView.vue`:**
- Add "Marketplace" tab (visible to all members)
- List cards showing task name, lister, bonus points, time remaining
- "List on Marketplace" action on user's own pending tasks
- "Claim" button on others' listings

---

### Step 21: Smart Suggestions

**Context:** From project plan Phase 4. Background job generates personalised suggestions stored as `Notification` rows. Users can accept or dismiss from their dashboard.

**Backend — `SmartSuggestionService`:**

```python
class SmartSuggestionService:
    def generate_for_group(self, group: Group) -> int:
        """Generate suggestions for all members. Returns count created."""
        ...
```

Four suggestion types:

**1. Pattern Recognition** — analyse `TaskOccurrence` history per user per template:
- If user completed same task ≥3 times on same day-of-week → emit notification: "You usually do [task] on Sundays — want it assigned to you this week?"
- Emit as `suggestion_pattern` notification with `action_url=/tasks`

**2. Availability-based batching** — check user's `Event` rows for free blocks (no `blocks_availability=True` events):
- If user has 2+ hour free block in next 48h and has ≥2 unassigned tasks → emit: "You're free Saturday morning — want to knock out these 3 tasks?"

**3. Preference-based open tasks** — check `TaskPreference` for high-scored templates with unassigned occurrences:
- If `TaskPreference.score >= 1` and matching occurrence is unassigned → emit: "There's a [task] you like available — want it?"

**4. Fairness rebalancing** — check `UserStats.total_tasks_completed` distribution:
- If user is >20% below group average → emit: "You've done fewer tasks this month — take an extra one for bonus points?"

**Backend — Celery beat job:**
```python
@shared_task
def generate_smart_suggestions():
    """Daily at 08:00 — generate suggestions for all active groups."""
    ...
```

Add to `CELERY_BEAT_SCHEDULE`: `{'task': 'chore_sync.tasks.generate_smart_suggestions', 'schedule': crontab(hour=8, minute=0)}`

**Frontend:** Smart suggestion notifications already render via the notification drawer. No new UI needed unless a dedicated "Suggestions" view is desired.

---

### Step 22: Additional Deadline Reminders + New Badge Criteria

#### 22a. Additional Reminder Windows

**Context:** Project plan specifies 4 windows: 24h before, 3h before, at-due-time, 1h overdue. Currently only 24h and overdue are implemented.

In `tasks.py` `dispatch_deadline_reminders`:
```python
# Add 3-hour window
three_hours = TaskOccurrence.objects.filter(
    status__in=['pending', 'snoozed'],
    deadline__gte=now + timedelta(hours=2, minutes=55),
    deadline__lte=now + timedelta(hours=3, minutes=5),
    reminder_3h_sent=False,  # new field
)
# Add at-due-time window
at_due = TaskOccurrence.objects.filter(
    status__in=['pending', 'snoozed'],
    deadline__gte=now - timedelta(minutes=5),
    deadline__lte=now + timedelta(minutes=5),
    reminder_due_sent=False,  # new field
)
```

Add boolean flags to `TaskOccurrence` model (1 migration):
- `reminder_3h_sent = BooleanField(default=False)`
- `reminder_due_sent = BooleanField(default=False)`

#### 22b. New Badge Criteria Types

Add 3 new criteria keys to `GamificationService.evaluate_badges`:

| Criteria key | Measures | Badge |
|---|---|---|
| `early_completions` | count of occurrences completed before deadline | "Early Bird" 🐦 |
| `emergency_accepts` | count of emergency reassignments accepted | "Team Player" 🤝 |
| `swap_completions` | count of accepted task swaps | "Negotiator" 🤝 |

Add these to `badges.json` and re-run `seed_badges.py`.

Increment `TaskOccurrence` counters on relevant events in `TaskLifecycleService`.

---

### Step 23: Stats Visualizations

**Context:** Backend stats endpoints already exist (`/api/users/me/stats/`, `/api/groups/<pk>/stats/`). Frontend only shows raw numbers. Project plan specifies Chart.js visualizations.

**Install:**
```bash
npm install chart.js vue-chartjs
```

**Frontend — new components:**
- `components/charts/TasksOverTimeChart.vue` — line chart of tasks completed per week (last 8 weeks)
- `components/charts/CategoryBreakdownChart.vue` — bar chart of tasks by category
- `components/charts/FairnessChart.vue` — horizontal bar per member showing fairness score / task count
- `components/charts/CompletionHeatmap.vue` — 7×N grid of completion counts by day-of-week

**Frontend — integrate into:**
- `UpdateProfileView.vue` — personal line chart + category breakdown
- `GroupDetailView.vue` leaderboard tab — fairness chart + completion heatmap

**Backend — extend stats endpoints** to return time-series data needed by charts:
- `/api/users/me/stats/` → add `weekly_completions: [{week: "2025-W10", count: 5}, ...]` (last 8 weeks)
- `/api/groups/<pk>/stats/` → add `per_member_totals: [{user_id, username, total, points}, ...]`

---

### Step 24: Notification Preferences

**Context:** Project plan mentions letting users configure which notification types they receive and quiet hours.

**Backend — new model `NotificationPreference`:**
```python
class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_prefs')
    # Per-type opt-out flags
    deadline_reminders   = models.BooleanField(default=True)
    task_assigned        = models.BooleanField(default=True)
    task_swap            = models.BooleanField(default=True)
    emergency_reassign   = models.BooleanField(default=True)
    badge_earned         = models.BooleanField(default=True)
    marketplace_activity = models.BooleanField(default=True)
    smart_suggestions    = models.BooleanField(default=True)
    # Quiet hours (user's local time)
    quiet_hours_enabled  = models.BooleanField(default=False)
    quiet_start          = models.TimeField(null=True, blank=True)  # e.g. 22:00
    quiet_end            = models.TimeField(null=True, blank=True)  # e.g. 08:00
```

**Backend — enforce in `emit_notification()`:**
- Load `NotificationPreference` for recipient
- Skip if the type flag is False
- Skip if current time (in user's timezone) is within quiet hours

**Backend — endpoint:**
- `GET/PATCH /api/users/me/notification-preferences/`

**Frontend — `UpdateProfileView.vue`:**
- Add "Notification Settings" section
- Toggle per type + quiet hours time pickers

---

### Step 25: Security Hardening

**Files:** `backend/chore_sync/settings.py`, `backend/chore_sync/models.py`, `backend/chore_sync/api/views.py`

**Actions:**
1. **Fix SSE 403 (`/api/events/stream/`)** — `EventStreamAPIView` returns 403 for all requests under ASGI/Daphne. Root cause: the SSE generator uses `StreamingHttpResponse` with a blocking `queue.get(timeout=25)` which doesn't interact correctly with ASGI lifecycle. Fix options:
   - Convert to an async Django view using `StreamingHttpResponse` with an async generator
   - Or replace SSE entirely with WebSocket (already implemented via `/ws/chores/`) — disable the SSE endpoint and route all real-time updates through the WS consumer
   - Additionally: the retry loop in the frontend (`CalendarView.vue`) must not retry on 403 (auth failure); add auth check before starting the stream

2. Add `django-ratelimit` to requirements; apply `@ratelimit(key='ip', rate='10/m')` to auth endpoints (`/api/auth/login/`, `/api/auth/register/`)

3. Set `CORS_ALLOW_ALL_ORIGINS = False` in production (already `False` by default)

4. Add production settings block:
   ```python
   if not DEBUG:
       SECURE_HSTS_SECONDS = 31536000
       SESSION_COOKIE_SECURE = True
       CSRF_COOKIE_SECURE = True
       SECURE_SSL_REDIRECT = True
   ```

5. File upload validation on photo proof (enforced in Step 19): max 5 MB, MIME whitelist (`image/jpeg`, `image/png`, `image/webp`)

6. Add `expires_at` check to `TaskSwap` accept endpoint — reject expired swaps at the API layer, not just via DB constraint

7. Enforce emergency reassign monthly limit server-side (3/month per user per group) — currently only a comment in the service

---

### Step 26: Fairness Algorithm Fixes + Calendar Availability in Assignment

#### 26a. Fix `time_based` Fairness Algorithm

**Problem:** Current implementation uses "days since last assignment" (rotation-style). Project plan defines `time_based` as tracking **total minutes of chore time** per user using `TaskTemplate.estimated_time_to_complete`.

**Fix in `GroupOrchestrator.compute_assignment_matrix`:**
```python
elif group.fairness_algorithm == 'time_based':
    # Sum estimated_time_to_complete for all completed + pending occurrences this user is assigned
    from django.db.models import Sum
    total_minutes = TaskOccurrence.objects.filter(
        assigned_to=user,
        template__group=group,
        status__in=['completed', 'pending', 'snoozed'],
    ).aggregate(total=Sum('template__estimated_time_to_complete'))['total'] or 0
    score = total_minutes  # lower = higher assignment priority
```

#### 26b. Calendar Availability in Assignment

**Problem:** `assign_occurrence` calls `compute_assignment_matrix` but ignores the user's blocked calendar slots. A user with a full calendar can still be assigned tasks during their busy periods.

**Add availability check in `assign_occurrence`:**
```python
def _is_user_available(self, user, deadline: datetime) -> bool:
    """Return False if user has a calendar event blocking availability at task deadline time."""
    from chore_sync.models import Event
    window_start = deadline - timedelta(hours=1)
    window_end   = deadline + timedelta(hours=1)
    return not Event.objects.filter(
        calendar__user=user,
        calendar__include_in_availability=True,
        blocks_availability=True,
        start__lt=window_end,
        end__gt=window_start,
    ).exists()
```

Filter out unavailable users before running the fairness matrix. If all users are unavailable, fall back to the fairness matrix without the availability filter (task must still be assigned).

---

### Step 27: TaskAssignmentHistory Model

**Context:** Project plan specifies a full history log for every assignment event. Used by Smart Suggestions (Step 21) for pattern recognition.

**New model:**
```python
class TaskAssignmentHistory(models.Model):
    user              = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignment_history')
    task_template     = models.ForeignKey(TaskTemplate, on_delete=models.SET_NULL, null=True, related_name='assignment_history')
    task_occurrence   = models.ForeignKey(TaskOccurrence, on_delete=models.CASCADE, related_name='assignment_history')
    assigned_at       = models.DateTimeField(auto_now_add=True)
    completed         = models.BooleanField(default=False)
    completed_at      = models.DateTimeField(null=True, blank=True)
    was_swapped       = models.BooleanField(default=False)
    was_emergency     = models.BooleanField(default=False)
    was_marketplace   = models.BooleanField(default=False)

    class Meta:
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['user', 'task_template', 'assigned_at']),
        ]
```

**Wire into `TaskLifecycleService`:**
- `assign_occurrence` → create history row
- `toggle_occurrence_completed` → update `completed=True, completed_at=now`
- `respond_to_swap_request` (accept) → set `was_swapped=True` on both rows
- `accept_emergency` → set `was_emergency=True` on new row
- `MarketplaceService.claim_task` → set `was_marketplace=True` on new row

---

### Step 28: PWA (Progressive Web App — Mobile Install)

**Context:** Yes — PWA is primarily for phones. It lets users install ChoreSync to their home screen like a native app, with offline support and push notifications. No App Store required.

**What it provides:**
- Install prompt on Android/iOS: "Add to Home Screen"
- App icon on home screen, launches full-screen (no browser chrome)
- Offline fallback page when network is unavailable
- Background sync for task completions made offline
- (Optional) Web Push notifications — richer than in-app only

**Implementation:**

**`frontend/public/manifest.json`:**
```json
{
  "name": "ChoreSync",
  "short_name": "ChoreSync",
  "description": "Intelligent household chore synchronisation",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1976d2",
  "icons": [
    {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png"}
  ]
}
```

**`frontend/public/sw.js`** (service worker):
- Cache app shell on install
- Network-first strategy for API calls
- Cache-first for static assets
- Offline fallback page for navigation requests

**`frontend/index.html`:** Add `<link rel="manifest" href="/manifest.json">` and `<meta name="theme-color" content="#1976d2">`.

**`frontend/src/main.ts`:** Register service worker:
```typescript
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js');
}
```

**Icons needed:** Create `frontend/public/icons/icon-192.png` and `icon-512.png` (ChoreSync logo).

**Vite PWA plugin** (simpler alternative):
```bash
npm install -D vite-plugin-pwa
```
Configure in `vite.config.ts` — auto-generates service worker and manifest, handles cache versioning.

