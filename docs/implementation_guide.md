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

### Step 1: Fix Architecture (Blocker — Do First)

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

### Step 2: Fix Data Model Gaps

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

### Step 3: OAuth Token Encryption

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

### Step 8: Task Lifecycle Features (Snooze, Swap, Emergency Reassign)

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

### Step 9: Gamification (Streaks, Points, Badges, Leaderboard)

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

### Step 10: Notification Delivery + WebSocket Integration

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

### Step 11: Group Proposal / Voting Endpoints

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

### Step 12: Stats Dashboard Endpoints

**Files:** new `backend/chore_sync/api/stats_router.py`, `backend/chore_sync/services/insights_service.py`

**Endpoints:**
- `GET /api/users/me/stats/` — return `UserStats` for the requesting user across all households
- `GET /api/users/me/badges/` — return `UserBadge.objects.filter(user=request.user).select_related('badge')`
- `GET /api/groups/{id}/stats/` — household-level aggregates: total tasks, completion rate, most-completed task, fairness distribution

---

### Step 13: Frontend Wiring

**Files:** `frontend/src/controllers/`, `frontend/src/services/api.ts`

**Actions:**
1. Implement `GroupDetailController.ts` — calls `GET /api/groups/{id}/`, `GET /api/groups/{id}/tasks/`, `GET /api/groups/{id}/members/`
2. Implement `MyTasksController.ts` — calls `GET /api/users/me/tasks/`; exposes snooze/complete/swap actions
3. Wire `NotificationSocketService.ts` to the new Django Channels WebSocket endpoint
4. Update Pinia `auth.ts` store to store `user_id` and `household_ids` (currently only stores `isAuthenticated: bool`)
5. Add PWA manifest: `frontend/public/manifest.json` with app name, icons, `display: standalone`

---

### Step 14: Outlook Calendar Sync

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

### Step 15: Dark Mode

**Files:** `frontend/src/main.ts`, `frontend/src/App.vue`, `frontend/src/quasar-variables.sass`

**Actions:**
1. Enable Quasar dark plugin in `main.ts`: `app.use(Quasar, { plugins: { Dark } })`
2. Add a dark mode toggle button in `App.vue` toolbar: `$q.dark.toggle()`
3. Persist the user's preference to `localStorage` and restore it on app startup via `$q.dark.set(stored)`
4. Add dark-mode overrides to `quasar-variables.sass` for any custom colours that don't invert correctly with Quasar's defaults
5. Test all 12 views in dark mode for readability

---

### Step 16: Security Hardening

**Files:** `backend/chore_sync/settings.py`, `backend/chore_sync/models.py`

**Actions:**
1. Add `django-ratelimit` to requirements; apply `@ratelimit(key='ip', rate='10/m')` to auth endpoints
2. Encrypt `ExternalCredential.secret` (Step 3)
3. Set `CORS_ALLOW_ALL_ORIGINS = False` in production
4. Add `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` to settings for production
5. Add file upload validation on photo proof: enforce max 5MB, MIME type whitelist (`image/jpeg`, `image/png`, `image/webp`)
6. Add `expires_at` check to `TaskSwap` in the accept endpoint (reject expired swap attempts)
7. Enforce emergency reassign monthly limit check server-side

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
| P4 | Step 14 (Outlook Calendar Sync) | Microsoft login done; Graph API calendar sync remaining |
| P4 | Step 15 (Dark Mode) | Polish — Quasar Dark plugin + localStorage persistence |
| P4 | Step 16 (Security Hardening) | Pre-production |
