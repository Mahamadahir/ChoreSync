# Deep Technical Critique

> **Status key:** ✅ Fixed | ⚠️ Known / Deliberate | 🔲 Pending

---

## 1. Partially Implemented Features

### Mobile SSO ✅ Fixed

- What is implemented:
  - The backend supports Google and Microsoft sign-in at [`backend/chore_sync/api/views.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/api/views.py) and [`backend/chore_sync/services/auth_service.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/services/auth_service.py).
  - The mobile auth service exposes `loginWithGoogle` and `loginWithMicrosoft` in [`mobile/src/services/authService.ts`](/home/mahamad/Projects/ChoreSync/mobile/src/services/authService.ts).
- **Fix applied:**
  - New backend endpoints `POST /api/auth/google/mobile/` and `POST /api/auth/microsoft/mobile/` in [`backend/chore_sync/api/jwt_views.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/api/jwt_views.py) accept an `id_token` and return `{ access, refresh, email_verified }` (JWT pair, not a session cookie).
  - `sign_in_with_google()` in [`backend/chore_sync/services/auth_service.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/services/auth_service.py) now accepts `extra_audiences` kwarg so mobile client IDs (iOS/Android) are validated alongside the web client ID.
  - `GOOGLE_MOBILE_CLIENT_IDS` setting added to [`backend/chore_sync/settings.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/settings.py) (comma-separated list of mobile client IDs).
  - `expo-auth-session` (~6.0.3) installed in mobile; `WebBrowser.maybeCompleteAuthSession()` wired up.
  - Both `LoginScreen.tsx` and `SignUpScreen.tsx` now use `Google.useAuthRequest` + `useAuthRequest` (Microsoft) with `ResponseType.IdToken` to obtain real ID tokens from the provider browser flow.
  - Mobile [`authService.ts`](/home/mahamad/Projects/ChoreSync/mobile/src/services/authService.ts) `loginWithGoogle`/`loginWithMicrosoft` now post to the new `/mobile/` endpoints.
  - Required env vars documented in [`mobile/.env.example`](/home/mahamad/Projects/ChoreSync/mobile/.env.example).

### Mobile Calendar Flows ✅ Fixed

- **Fix applied:**
  - `GoogleCalendarCallbackAPIView` changed to `AllowAny`; user identity now comes from a signed `state` param (`django.core.signing.dumps`, salt `google_oauth`, 10 min expiry) embedded by `GoogleCalendarAuthURLAPIView` when `?mobile=true` is passed. Web flow (no state) falls back to session-based PKCE as before.
  - `OutlookCalendarService.build_auth_url(mobile=True)` embeds `mobile: True` in the existing signed state; `OutlookCalendarCallbackAPIView` reads the flag and redirects to `MOBILE_CALENDAR_REDIRECT_URI?provider=outlook` instead of the web frontend.
  - New `GET /api/calendar/status/` endpoint (`CalendarStatusAPIView`) returns `{ google: { connected }, outlook: { connected } }` by checking `ExternalCredential` existence directly — no longer fragile against empty event lists.
  - `MOBILE_CALENDAR_REDIRECT_URI = env('MOBILE_CALENDAR_REDIRECT_URI', default='choresync://calendar/connected')` added to `settings.py` and documented in `secrets.env`.
  - `calendarService.ts` rewritten: `googleAuthUrl`/`outlookAuthUrl` pass `?mobile=true`; `googleSelect`/`outlookSelect` now send the correct array-of-objects payload; `googleList()`, `outlookList()`, and `status()` methods added with TypeScript types.
  - `CalendarScreen.tsx` updated: uses `calendarService.status()` on mount; OAuth connect uses `WebBrowser.openAuthSessionAsync(url, 'choresync://')` which intercepts the deep-link redirect; "coming soon" alert replaced with a full `CalendarPickerModal` (availability `Switch` per calendar, Outlook task write-back radio) for both Google and Outlook.

### Proposal Enforcement Logic ✅ Fixed

- **Fix applied:** `GroupTaskTemplateListCreateAPIView.post` now rejects direct task-template creation with HTTP 403 when `task_proposal_voting_required=True` and the caller is not a moderator.
- Moderators retain direct-creation ability to support the parent-child governance model without workflow overhead.
- Note: `group_type = "parent_child" | "peer_peer"` as a formal model field remains a future improvement; the immediate enforcement gap is closed.

### Outlook Sync Field Mismatches ✅ Fixed

- **Fixes applied** in [`backend/chore_sync/services/outlook_calendar_service.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/services/outlook_calendar_service.py):
  - All `Event.objects.filter/update_or_create` calls now use `external_event_id` (model field) instead of `external_id` (non-existent).
  - `event.external_id = ...` / `save(update_fields=["external_id"])` in `push_created_event` corrected to `external_event_id`.
  - `push_updated_event` and `push_deleted_event` guard checks updated to `event.external_event_id`.
  - Invalid `"user": self.user` default removed from `Event.objects.update_or_create` — `Event` has no `user` field; user context is via `calendar.user`.
  - Note: `calendar.external_id` references are correct — `Calendar` model does have `external_id`.

### AI Assistant Domain Mismatches ✅ Fixed

- **Fix applied:** Removed `claimed_by__isnull=True` from marketplace listing query in chatbot (`MarketplaceListing` has no such field). Active/unclaimed listings are already filtered by `expires_at__gt=now()`.
- **Fix applied:** All direct model writes in the chatbot now route through the service layer:
  - `_handle_create_task` → `TaskTemplateService().create_template()`
  - `_handle_propose_task` → `ProposalService().create_proposal()` (also sends vote notifications to group members)
  - `_handle_join_group` → `GroupOrchestrator().join_by_code()` (validates not-already-member)
  - Marketplace branch in `_handle_choose_option` → `MarketplaceService().list_task()`

---

## 2. System Limitations

### JWT Auth on Protected Views ✅ Fixed (verified)

- All API routers now use `authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]` — task, group, marketplace, notification, task-template, preference, stats, proposal routers all confirmed.

### GET /api/tasks/{id}/ Not Implemented ✅ Fixed (verified)

- `TaskOccurrenceDetailAPIView` has a `def get` implementation at [`backend/chore_sync/api/task_router.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/api/task_router.py).

### Group Settings Field Name Mismatches ✅ Fixed (verified)

- Mobile already reads `task_proposal_voting_required` and sends matching field names. The `voting_enabled` mismatch cited in the original audit is not present in current code.

### Mobile Group Delete via `{ deleted: true }` ✅ Fixed (verified)

- Mobile `GroupSettingsScreen` calls `groupService.leave(groupId)` — a real `POST /api/groups/{id}/leave/` endpoint. No PATCH `{ deleted: true }` pattern exists in current code.

### Stale Field: `template__estimated_time_to_complete` ✅ Fixed

- **Fix applied** in [`backend/chore_sync/services/group_service.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/services/group_service.py): `time_based` fairness algorithm now aggregates on `template__estimated_mins` (the actual model field).

### Local AI (Ollama) Dependency ✅ Fixed

- **Fix applied:** `OLLAMA_URL` and `OLLAMA_MODEL` are now env-var driven in `settings.py`, with local Ollama as the default.
- Set `OLLAMA_URL` to any OpenAI-compatible endpoint (OpenRouter, Groq, etc.) in staging/production — the request payload shape is identical.
- Examples documented as comments in `backend/secrets.env`.

### InMemoryChannelLayer ✅ Fixed

- **Fix applied:** `CHANNEL_LAYERS` in `settings.py` now auto-selects the backend based on `CELERY_BROKER_URL`:
  - If set → `channels_redis.core.RedisChannelLayer` using the same Redis URL as Celery
  - If unset (local dev with no Redis) → `channels.layers.InMemoryChannelLayer` as before
- `channels-redis>=4.2.0` added to `requirements.txt`.
- Run `pip install -r requirements.txt` to install.

### Sync Reliability and Conflict Handling 🔲 Pending

- No shared reconciliation strategy across Google and Outlook providers.
- Partial fix achieved by correcting Outlook field mismatches (see above); broader retry/conflict strategy deferred.

---

## 3. Architectural Weaknesses

- **Service-layer bypasses in assistant** — fully resolved; all intent handlers route through service layer.
- **Calendar integration normalisation** — Outlook field mismatches fixed; provider-level schema normalisation is a future task.
- **Governance enforcement** — proposal gate now enforced server-side; formal `group_type` model field is a future improvement.
- **Client contract fragmentation** — mobile calendar selection payload mismatch is a known issue (see above).

---

## 4. Prioritised Roadmap

### Done ✅
- JWT auth on all protected API views
- `GET /api/tasks/{id}/` implementation
- Group settings field parity (mobile)
- Mobile group leave (correct endpoint)
- `estimated_time_to_complete` → `estimated_mins` in `time_based` fairness
- Outlook `external_id` → `external_event_id` throughout sync and write-back
- Chatbot `claimed_by__isnull` removed (invalid field)
- `task_proposal_voting_required` enforced server-side in template creation
- Mobile SSO (Google + Microsoft) with `expo-auth-session` and dedicated JWT endpoints
- AI Assistant service-layer bypass — all 4 direct model writes routed through services
- InMemoryChannelLayer → Redis-backed auto-selection via `CELERY_BROKER_URL`
- Ollama endpoint + model made configurable via `OLLAMA_URL` / `OLLAMA_MODEL` env vars

### High Priority 🔲

### Medium Priority 🔲
- Normalise provider event schemas across Google and Outlook (etag, change token, sync state).

### Low Priority / Future 🔲
- Add formal `group_type = "parent_child" | "peer_peer"` to `Group` model.
- Add governance presets at group creation time.
- Add sync observability, dashboards, and operator remediation tools.
- Add replay-aware real-time delivery for reconnecting clients.

## New Issues (Latest Audit) — Partially Resolved

### Executive Summary

- Codebase health: medium → improving. Most Level 1 breaks have been fixed in this pass.
- Key risks resolved in this pass:
  - ✅ Outlook connection state now queries `provider="microsoft"` — status endpoint returns correct connected state.
  - ✅ Template deletion now writes a declared terminal status (`cancelled` added to `status_choices`).
  - ✅ Real-time chat now shows an explicit error alert when the socket is not open (mobile).
  - ⚠️ Mobile photo-proof upload UI does not yet exist — `uploadProof` service method is documented with the correct field name (`photo`) for when it is implemented.
- Remaining open items: notification deep-link completeness, Outlook writeback in Vue web, mobile task authoring, emergency reassign accept UI — see roadmap below.

### The "Broken Bridge" Table (Mismatches)

| Feature | Platform | The Mismatch | Impact |
| --- | --- | --- | --- |
| Outlook connected status ✅ Fixed | Backend + Vue + React Native | `CalendarStatusAPIView` now queries `provider="microsoft"` matching the stored credential key. | Fixed in `views.py`. |
| Photo-proof upload ⚠️ Upload UI absent | React Native + Backend | The `uploadProof` service method is documented to use `photo` (correct field). The upload UI does not yet exist in `TaskDetailScreen.tsx` — the prior audit pointed to code that was removed. | Field name documented in `taskService.ts`; UI implementation is a future task. |
| Outlook task writeback selection | Vue + Backend | Web payload typing in [`calendarService.ts`](/home/mahamad/Projects/ChoreSync/frontend/src/services/calendarService.ts#L45) omits `is_task_writeback`, but backend selection logic depends on it in [`outlook_calendar_router.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/api/outlook_calendar_router.py#L128). Mobile includes the flag in [`mobile calendarService.ts`](/home/mahamad/Projects/ChoreSync/mobile/src/services/calendarService.ts#L32). | Writeback calendar choice is mobile-only; web silently falls back to the first writable calendar. |
| Task creation UX | React Native | The visible "New Task" CTA in [`GroupDetailScreen.tsx`](/home/mahamad/Projects/ChoreSync/mobile/src/screens/groups/GroupDetailScreen.tsx#L514) routes to group settings, while mobile service methods for template creation exist but are never invoked in UI (`createTemplate`, `updateTemplate`, `generateOccurrences` in [`groupService.ts`](/home/mahamad/Projects/ChoreSync/mobile/src/services/groupService.ts#L33)). | Mobile appears to support task authoring but does not provide an end-to-end creation/edit flow. |
| Emergency reassignment acceptance | Backend + both clients | Endpoint exists at [`urls.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/urls.py#L179) and service wrappers exist in both clients, but repo-wide usage only shows declarations, not actual screen calls. | The emergency flow is only half-built: users can trigger emergencies but cannot complete the “accept” branch from either frontend. |

### Logical & Silent Fail Report

- Level 1: ✅ Fixed — Outlook state endpoint now queries `provider="microsoft"`.
  - Fix: `CalendarStatusAPIView` in `views.py` changed from `provider="outlook"` to `provider="microsoft"`. Docstring updated to reflect both canonical provider keys.

- Level 1: ⚠️ Partially addressed — mobile photo-proof upload UI does not currently exist.
  - Finding: `TaskDetailScreen.tsx` no longer contains a FormData upload call. The `taskService.uploadProof` method is documented with the correct field name (`photo`). When the upload UI is implemented it must use `formData.append('photo', ...)`.
  - Remaining: build the upload UI in `TaskDetailScreen.tsx`.

- Level 2: ✅ Fixed (mobile) — `sendChatMessage` in `GroupDetailScreen.tsx` now shows an Alert when the WebSocket is not open. Web (Vue) is a lower-priority fix as the web socket is more reliably connected via the persistent `watch()` hook; web chat send is noted as a future improvement.

- Level 2: ✅ Fixed — `'cancelled'` added to `TaskOccurrence.status_choices` in `models.py`. Migration required (`python manage.py makemigrations && migrate`). Docstring in `task_template_service.py` updated to reflect the correct terminal state wording.

- Level 2: ✅ Fixed — `_TYPE_TO_PREF` in `notification_service.py` now maps `'emergency_reassignment'` (the emitted type) to the `'emergency_reassign'` preference field. The legacy `'emergency_reassign'` key is retained for safety.

- Level 2: ✅ Fixed — `_handle_snooze_all()` now logs each failure with `logger.warning`, tracks which tasks failed, and returns a user-facing message naming any tasks that could not be snoozed.

- Level 3: Daily occurrence generation logs failures but leaves per-template drift unresolved.
  - Evidence: [`backend/chore_sync/tasks.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/tasks.py#L64)
  - Issue: one template failing during the daily job is only logged; there is no retry, dead-letter, or health signal.
  - Runtime effect: recurring-task gaps can accumulate quietly until a user notices missing chores.

### Non-Functional / Incomplete Features

- Mobile task authoring is incomplete.
  - `createTemplate`, `updateTemplate`, and `generateOccurrences` exist in [`mobile/src/services/groupService.ts`](/home/mahamad/Projects/ChoreSync/mobile/src/services/groupService.ts#L33), but there is no creation/edit screen wired to them, and the "New Task" button routes to settings instead of task creation.

- Emergency reassignment is only partially implemented end to end.
  - Create path exists (`/api/tasks/<id>/emergency-reassign/`) and the web task view calls it.
  - Acceptance path exists (`/api/tasks/<id>/accept-emergency/`) but no screen in either frontend invokes it.

- Outlook writeback selection is not cross-platform.
  - Mobile exposes `is_task_writeback`.
  - Web does not, so the backend silently chooses a fallback calendar instead of honoring explicit user intent.

- Group analytics are backend-only.
  - `GET /api/groups/<uuid>/stats/` and `GET /api/groups/<uuid>/assignment-matrix/` are defined in [`urls.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/urls.py#L164), and both clients define service wrappers, but there is no actual UI usage.

### Backend Integrity Report

- Unused models:
  - No fully orphaned Django model classes were found. Most models are at least referenced by services, admin, or background jobs.

- APIs not connected to any frontend screen:
  - `/api/groups/<uuid>/assignment-matrix/`
  - `/api/groups/<uuid>/stats/`
  - `/api/task-templates/<id>/generate-occurrences/`
  - `/api/tasks/<id>/accept-emergency/`
  - `/api/notifications/history/`
  - These are present in routes and service wrappers, but repo-wide usage only shows declarations, not screen-level calls.

- Models/features not fully exposed across the stack:
  - `Calendar.is_task_writeback` is honored by backend and mobile, but not by Vue.
  - ✅ Fixed — Badge data is now surfaced in React Native. `ProfileScreen.tsx` gained an Achievements section (horizontal scrollable chips) with a bottom-sheet detail modal showing emoji, name, description, points, and earned date+time. `_serialize_badge()` in `insights_service.py` now includes the `emoji` field. Vue badge chips were also made clickable with a `q-dialog` detail modal (same pass).

- Data-flow break:
  - `TaskTemplate -> TaskOccurrence -> delete_template()` currently mutates occurrences into an undeclared status, so the lifecycle contract is not preserved after template removal.

### The Zombie List

- Unused files:
  - No confidently orphaned top-level source files were identified after import/reference search.

- Dead or effectively dead code paths:
  - [`frontend/src/services/api.ts`](/home/mahamad/Projects/ChoreSync/frontend/src/services/api.ts#L26) `groupApi.stats`
  - [`frontend/src/services/api.ts`](/home/mahamad/Projects/ChoreSync/frontend/src/services/api.ts#L51) `taskApi.acceptEmergency`
  - [`frontend/src/services/api.ts`](/home/mahamad/Projects/ChoreSync/frontend/src/services/api.ts#L74) `notificationApi.history`
  - [`mobile/src/services/groupService.ts`](/home/mahamad/Projects/ChoreSync/mobile/src/services/groupService.ts#L29) `stats`
  - [`mobile/src/services/groupService.ts`](/home/mahamad/Projects/ChoreSync/mobile/src/services/groupService.ts#L45) `generateOccurrences`
  - [`mobile/src/services/groupService.ts`](/home/mahamad/Projects/ChoreSync/mobile/src/services/groupService.ts#L81) `assignmentMatrix`
  - [`mobile/src/services/taskService.ts`](/home/mahamad/Projects/ChoreSync/mobile/src/services/taskService.ts#L25) `acceptEmergency`

- Orphaned endpoints:
  - [`backend/chore_sync/urls.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/urls.py#L164) assignment matrix
  - [`backend/chore_sync/urls.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/urls.py#L170) generate occurrences
  - [`backend/chore_sync/urls.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/urls.py#L179) accept emergency
  - [`backend/chore_sync/urls.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/urls.py#L194) notification history

### Documentation Redline

- Incorrect comment/docstring:
  - [`backend/chore_sync/api/views.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/api/views.py#L967)
  - Current: `Checks ExternalCredential existence directly rather than inferring from events.`
  - Problem: the implementation checks the wrong provider key for Outlook, so the docstring currently overstates correctness.
  - Corrected version: `Checks ExternalCredential existence directly for provider keys actually used by persisted credentials (google, microsoft).`

- Incorrect docstring:
  - [`backend/chore_sync/services/task_template_service.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/services/task_template_service.py#L84)
  - Current: `Soft-delete a template and cancel its pending occurrences.`
  - Problem: the implementation does not cancel via a declared lifecycle state; it writes `cancelled`, which is not in `TaskOccurrence.status_choices`.
  - Corrected version: `Soft-delete a template and transition pending occurrences into a declared terminal state; do not write undeclared status values.`

### Styling Drift

- Vue theming is partially bypassed by hardcoded chart and calendar colors.
  - Examples: [`frontend/src/components/charts/CategoryBreakdownChart.vue`](/home/mahamad/Projects/ChoreSync/frontend/src/components/charts/CategoryBreakdownChart.vue), [`frontend/src/views/CalendarView.vue`](/home/mahamad/Projects/ChoreSync/frontend/src/views/CalendarView.vue#L310)
  - Impact: charts and calendar affordances no longer inherit the CSS token system from [`frontend/src/design-system.css`](/home/mahamad/Projects/ChoreSync/frontend/src/design-system.css).

- React Native screens duplicate palette constants instead of using shared theme tokens.
  - Examples: [`mobile/src/screens/auth/SignUpScreen.tsx`](/home/mahamad/Projects/ChoreSync/mobile/src/screens/auth/SignUpScreen.tsx#L371), [`mobile/src/screens/profile/ProfileScreen.tsx`](/home/mahamad/Projects/ChoreSync/mobile/src/screens/profile/ProfileScreen.tsx#L25), [`mobile/src/screens/notifications/NotificationsScreen.tsx`](/home/mahamad/Projects/ChoreSync/mobile/src/screens/notifications/NotificationsScreen.tsx#L22)
  - Impact: the app carries multiple hand-maintained palettes despite already having [`mobile/src/theme/colors.ts`](/home/mahamad/Projects/ChoreSync/mobile/src/theme/colors.ts), which increases drift and makes visual fixes inconsistent.

### Verification Notes

- Static audit completed across backend, Vue, and React Native source.
- Runtime verification was limited because local dependencies are not installed in this workspace:
  - `python3 backend/manage.py check` failed with `ModuleNotFoundError: No module named 'django'`
  - `python3 -m pytest -q backend/chore_sync/tests` failed with `No module named pytest`

## New Issues (Latest Audit - Notification Deep Link Forensic Audit)

Existing issues were retained because unresolved prior findings still remain in the codebase, including the notification-preference mismatch for `emergency_reassignment`.

### Executive Summary

- Notification system health: fragile. The backend emits notifications reliably enough, but the deep-link contract is split across `action_url` plus optional foreign keys, with no single canonical target schema.
- Deep link reliability: low. Most task-centric notifications store `/tasks/<id>` as `action_url`, but Vue has no `/tasks/:id` route and React Native never consumes `action_url`.
- Cross-platform parity: poor. Vue can only follow raw path strings; React Native mostly treats notifications as read-state cards, not navigation affordances.
- Key architectural risk: realtime, REST, and model/type definitions disagree on payload shape, so a notification can be actionable when fetched from REST yet partially non-functional when delivered live.

### The Broken Notification Bridge Table

| Notification Type | Platform | The Mismatch | Impact |
| --- | --- | --- | --- |
| `task_assigned`, `deadline_reminder`, `emergency_reassignment`, accepted/declined `task_swap`, `suggestion_streak` | Vue + React Native | Backend stores `action_url="/tasks/<id>"` at `backend/chore_sync/tasks.py:114-120`, `backend/chore_sync/services/task_lifecycle_service.py:295-305`, `backend/chore_sync/services/task_lifecycle_service.py:788-804`, `backend/chore_sync/services/task_lifecycle_service.py:866-940`, but Vue only defines `/tasks` in `frontend/src/main.ts:30-35` and mobile ignores `action_url` in `mobile/src/screens/notifications/NotificationsScreen.tsx:109-218`. | Core task notifications mark as read but do not open the intended task detail end to end. |
| `task_proposal` | Vue + React Native | Backend emits `group_id` and `task_proposal_id` with no `action_url` in `backend/chore_sync/services/proposal_service.py:185-195`. Vue click handler only routes when `action_url` exists in `frontend/src/App.vue:220-225`; mobile “Review Details” only marks read in `mobile/src/screens/notifications/NotificationsScreen.tsx:189-200`. | Proposal notifications render as actionable UI but never open proposal review on either platform. |
| `message` mention ✅ Fixed (Vue) | Vue + React Native | `GroupDetailView.vue` now initialises `tab` from `?tab=` route query, so `/groups/<id>?tab=chat` deep-links land on the chat tab. Mobile navigates to the group detail screen on message notification tap. | Fixed in `GroupDetailView.vue` and `NotificationsScreen.tsx`. |
| Realtime `task_swap`, `task_proposal`, `message` ✅ Fixed | Vue realtime path | Both WebSocket serializers (`_notifications_since`, `_serialize_notification`) in `consumers.py` now include `task_swap_id`, `task_proposal_id`, `message_id`. | Fixed in `consumers.py`. |
| `group_invite` ✅ Fixed | Vue + React Native | `group_service.py` now calls `NotificationService().emit_notification()` for invites, giving realtime WS/SSE fan-out, preference enforcement, and `action_url=/groups/<id>`. | Fixed in `group_service.py`. |
| `calendar_sync_complete` ✅ Fixed | Vue + React Native | Added to `Notification.TYPE_CHOICES` in `models.py` and to `NotificationType` + `NOTIF_CONFIG` in mobile. | Fixed. |

### Deep Link Failure Report

1. Level 1: ✅ Fixed — Vue notification click handler now translates `/tasks/<id>` → `/tasks` (list), `/groups/<id>?tab=X` → group-detail with tab query, and `group_id` fallback for invite/message types. Wrapped in try/catch to handle stale/deleted entity routes gracefully. Mobile `NotificationsScreen` now navigates to `TaskDetail` for task-centric notifications and `GroupDetail` for group-centric ones via cross-tab `navigation.navigate('TasksTab', ...)`.

2. Level 1: ✅ Fixed — Both WebSocket serializers in `consumers.py` now include `task_swap_id`, `task_proposal_id`, `message_id`, bringing realtime payloads to parity with the REST serializer.
   - Evidence:
     - REST shape: `backend/chore_sync/api/notification_router.py:153-167`
     - WebSocket replay shape: `backend/chore_sync/django_app/consumers.py:247-259`
     - WebSocket push shape: `backend/chore_sync/django_app/consumers.py:342-352`
     - SSE shape: `backend/chore_sync/services/notification_service.py:80-94`, `backend/chore_sync/api/views.py:816-830`
   - Exact failure:
     - REST returns `task_swap_id`, `task_proposal_id`, and `message_id`.
     - WebSocket delivery drops all three.
     - SSE uses `notification_type` while REST and WebSocket use `type`.
   - Runtime result:
     - A fetched swap notification can be actionable, while the same notification delivered live lacks the identifiers needed for swap response or entity-specific navigation.
     - The system has no stable backend-to-frontend contract for notification targets.
   - Affects: Vue realtime path directly, both platforms architecturally.

3. Level 1: ✅ Fixed — `NotificationsScreen.tsx` now navigates on card tap. Task-centric types (`task_assigned`, `deadline_reminder`, `emergency_reassignment`, `marketplace_claim`) navigate to `TasksTab > TaskDetail`. Group-centric types (`message`, `group_invite`, `task_proposal`) navigate to `GroupsTab > GroupDetail`. Suggestion types navigate to `TasksTab > Tasks`. “Review Details” and “View Tasks” action buttons also trigger navigation.

4. Level 1: ✅ Fixed (Vue web tab) — `GroupDetailView.vue` now reads `?tab=` from the route query on mount. `/groups/<id>?tab=chat` correctly activates the chat tab. Mobile navigates to group detail; chat-tab activation on mobile is a future improvement (requires passing tab param through cross-stack navigation).

5. ✅ Fixed — Optimistic read/dismiss state mutations now roll back on failure (mobile).
   - Fix: `notificationStore.ts` gained a `markUnread(id)` action. `handleMarkRead` in `NotificationsScreen.tsx` now calls `storeMarkUnread(id)` in the catch block to revert the optimistic update. `handleSwapDecline` no longer calls `storeDismiss` in the catch block; instead it shows an error alert so the user can retry. Vue's `markRead` was already non-optimistic (API call first, state update after) — no change needed there.

6. Level 2: ✅ Fixed — `Notification.TYPE_CHOICES` in `models.py` now includes `suggestion_streak` and `calendar_sync_complete`. Mobile `NotificationType` union and `NOTIF_CONFIG` updated to match. `task_suggestion` retained in both with a legacy comment (exists in DB rows from prior emits).

7. Level 2: ✅ Fixed — `group_service.py` invite path replaced direct `Notification.objects.create()` with `NotificationService().emit_notification()`, giving realtime WebSocket/SSE fan-out, preference enforcement, and `action_url=/groups/<id>`.

### Non-Functional / Incomplete Notification Flows

- `task_proposal` ✅ Partially fixed — Mobile now navigates to GroupDetail on proposal card tap. Vue navigates to group-detail via `group_id` fallback. Full proposal-review deep-link (navigating directly to the proposal vote UI) is a future task.

- `message` mentions ✅ Partially fixed — Vue now reads `?tab=chat` from route query so mention notifications land on the chat tab. Mobile navigates to group detail. Direct scroll-to-message is a future task.

- `marketplace_claim` is created but non-functional as a deep link.
  - Backend stores `task_occurrence_id` only in `backend/chore_sync/services/marketplace_service.py:44-53` and `backend/chore_sync/services/marketplace_service.py:101-115`.
  - No platform maps marketplace notifications to marketplace screens or to the affected task detail reliably.

- `badge_earned` is informational only.
  - No payload field points to a badge screen, and React Native has no badge screen in navigation.

- `group_invite` exists in storage but not as a complete notification flow.
  - No realtime delivery.
  - No route target.
  - No accept/join action from the notification itself.

- `calendar_sync_complete` is backend-only.
  - It can be created, but there is no dedicated client config, route mapping, or mobile type support.

- `task_suggestion` is effectively zombie notification vocabulary.
  - Present in model/mobile UI, absent from current emit sites.

### Backend Integrity Report

- Notification target contract is split and under-specified.
  - The backend sometimes sends `action_url`, sometimes sends only object IDs, and often sends both without saying which field is authoritative.
  - There is no normalized target object like `{ kind, entity_id, fallback_route, params }`.

- Realtime vs fetched payloads are inconsistent.
  - REST: `id`, `type`, `task_swap_id`, `task_proposal_id`, `message_id`, `action_url`.
  - WebSocket: `id`, `type`, `task_occurrence_id`, `action_url` only.
  - SSE: `notification_type` instead of `type`, includes some IDs, excludes `message_id`.

- Required deep-link fields are not populated consistently.
  - `task_proposal` has no `action_url`.
  - `marketplace_claim` has no `action_url`.
  - `badge_earned` has no destination metadata.
  - `group_invite` has no destination metadata and no service-layer fan-out.

- Existence and permission fallback is missing.
  - Notification click handlers do not guard deleted tasks, removed groups, stale swaps, or inaccessible proposals with a fallback screen or user-facing error.
  - Vue `handleNotificationClick()` has no `try/catch` around `router.push()` and no fallback UX in `frontend/src/App.vue:220-225`.

- Comments overstate reality.
  - `NotificationService.emit_notification()` says `action_url` is where a notification “should navigate to when clicked,” but that is only partly true on web and false on mobile.
  - `useAppForegroundRefresh` claims mobile re-fetch keeps the store up to date, but the hook is not used anywhere in `mobile/src`.

### The Zombie List

- Dead notification type vocabulary:
  - `task_suggestion` in `backend/chore_sync/models.py:1115` and `mobile/src/types/notification.ts:3` is not emitted by current backend code.

- Backend-only notification type:
  - `calendar_sync_complete` is emitted in `backend/chore_sync/tasks.py:365-372` but absent from model choices and mobile types.

- ✅ Fixed — Orphaned mobile realtime refresh hook now mounted:
  - `useAppForegroundRefresh` is now called inside `HomeScreen` — the root authenticated screen. It listens to AppState transitions and re-fetches `/api/notifications/` whenever the app returns to foreground.

- Stale frontend notification typing:
  - `frontend/src/services/NotificationSocketService.ts:20-30` omits `task_swap_id`, `task_proposal_id`, `message_id`, and `action_url` even though backend payloads may contain them.

- Redundant route-resolution logic by accident:
  - Backend encodes navigation partly as `action_url`, partly as FK IDs.
  - Vue relies only on `action_url`.
  - React Native ignores `action_url` and has no notification route mapper.
  - This guarantees drift because each layer effectively defines “where notifications go” differently.

### Documentation Redline

- ✅ Fixed — `action_url` docstring in `notification_service.py` updated to: "Optional web fallback path. Do not treat this as the canonical notification target; clients must resolve navigation from the structured FK fields."
- ✅ Fixed — `list_active_notifications` docstring corrected to "non-dismissed" (not "unread, non-dismissed").
- ✅ Fixed — SSE comment in `notification_service.py` updated to accurately describe CalendarView behaviour and that mobile does not subscribe to SSE.
- ✅ Fixed — `useAppForegroundRefresh.ts` docstring updated to "If mounted..." to accurately reflect that it requires explicit mounting.

### Verification Notes

- Static audit completed. All fixes in this pass have been applied directly to source.
- A Django migration is required for model changes: `python manage.py makemigrations && python manage.py migrate`.
- Runtime verification remains limited because backend dependencies are not installed in this workspace.

---

## Fix Pass Summary (2026-04-04)

### Issues verified as already fixed (pre-existing)

- Mobile SSO (Google + Microsoft)
- Mobile Calendar Flows (OAuth callback, status endpoint, picker)
- Proposal Enforcement Logic
- Outlook Sync Field Mismatches
- AI Assistant Domain Mismatches
- JWT Auth on all protected API views
- GET /api/tasks/{id}/ implementation
- Group Settings field parity (mobile)
- Mobile group delete (correct endpoint)
- `estimated_time_to_complete` → `estimated_mins`
- InMemoryChannelLayer → Redis auto-selection
- Ollama endpoint configurability

### Issues fixed in this pass

| Issue | Files Changed |
|-------|--------------|
| Outlook `CalendarStatusAPIView` queried `provider="outlook"` instead of `"microsoft"` | `backend/chore_sync/api/views.py` |
| `cancelled` missing from `TaskOccurrence.status_choices` | `backend/chore_sync/models.py` |
| Emergency notification preference key mismatch (`emergency_reassign` vs `emergency_reassignment`) | `backend/chore_sync/services/notification_service.py` |
| Group invite bypassed `NotificationService` pipeline (no realtime fan-out) | `backend/chore_sync/services/group_service.py` |
| `suggestion_streak` and `calendar_sync_complete` missing from `Notification.TYPE_CHOICES` | `backend/chore_sync/models.py` |
| WebSocket serializers missing `task_swap_id`, `task_proposal_id`, `message_id` | `backend/chore_sync/django_app/consumers.py` |
| `NotificationPayload` TypeScript type missing `action_url`, FK fields | `frontend/src/services/NotificationSocketService.ts` |
| Vue notification click handler: no try/catch, `/tasks/<id>` route missing, no `group_id` fallback | `frontend/src/App.vue` |
| `GroupDetailView.vue` ignored `?tab=` query param on mount | `frontend/src/views/GroupDetailView.vue` |
| Mobile chat send silently dropped messages when socket closed | `mobile/src/screens/groups/GroupDetailScreen.tsx` |
| Mobile `NotificationsScreen` card taps did not navigate | `mobile/src/screens/notifications/NotificationsScreen.tsx` |
| Mobile notification types missing `suggestion_streak`, `calendar_sync_complete`; `Notification` interface missing FK fields | `mobile/src/types/notification.ts`, `mobile/src/screens/notifications/NotificationsScreen.tsx` |
| `_handle_snooze_all` swallowed all exceptions silently | `backend/chore_sync/api/chatbot_router.py` |
| Photo-proof upload field name undocumented (upload UI absent) | `mobile/src/services/taskService.ts` (comment added) |
| Four incorrect docstrings/comments | `notification_service.py`, `task_template_service.py`, `useAppForegroundRefresh.ts` |

### Issues still unresolved

| Issue | Reason |
|-------|--------|
| Optimistic read/dismiss state without rollback (Level 2) | Low-risk UX polish; deferred |
| Vue web chat send gives no error if socket closed | Minor; web socket is reliably reconnected; deferred |
| Mobile `?tab=chat` not passed through cross-stack navigation | React Navigation cross-stack param passing is non-trivial; deferred |
| Mobile photo-proof upload UI not implemented | Feature work required; field name documented |
| Mobile task authoring (no create/edit screen) | Full screen implementation; deferred |
| Emergency reassign accept UI (no screen in either frontend) | Feature work; deferred |
| Outlook writeback (`is_task_writeback`) missing from Vue web calendar selection | Vue calendar select form update needed; deferred |
| Group analytics screens (`/api/groups/<uuid>/stats/`, assignment-matrix) | UI feature work; deferred |
| Sync reliability / conflict handling across providers | Architectural task; deferred |
| `useAppForegroundRefresh` not mounted anywhere | Should be mounted in HomeScreen or App root; deferred |

---

## New Issues (Latest Audit)

### Executive Summary

- Codebase health: Medium-low. The product has real full-stack breadth, but too many important paths still depend on best-effort behavior rather than guaranteed end-to-end success.
- Architectural maturity: Mixed. Service boundaries are improving, yet auth, observability, and cross-platform parity are still inconsistent enough to create real runtime risk.
- Key risks:
  - Level 1: the Vue app uses cookie-backed session auth on endpoints where CSRF enforcement is explicitly disabled.
  - Level 1: mobile photo-proof upload now exists, but the form field name is wrong and the feature hard-fails at runtime.
  - Level 2: task-template creation reports success even when initial occurrence generation fails.
  - Level 2: several Celery maintenance jobs suppress exceptions entirely, so sync drift and subscription failures can accumulate with no signal.

### The Broken Bridge Table (Mismatches)

| Feature | Platform | The Mismatch | Impact |
|---|---|---|---|
| Session-authenticated API protection | Vue + Django | Web client sends cookies with `withCredentials: true`, but protected routers use `CsrfExemptSessionAuthentication`, which skips CSRF enforcement. | Cross-site requests can hit authenticated state-changing endpoints if the browser session is present. |
| Photo-proof upload | React Native + Django | Mobile submits `photo_proof`, while backend only accepts `photo`. | Upload flow looks complete but fails with HTTP 400 in production use. |
| Task-template creation | Vue + Django | Template save is transactional enough to return `201`, but immediate occurrence generation is best-effort only. | Users can “create” chores that do not appear on task boards until a later background job succeeds. |
| Calendar resilience jobs | Backend only | Renewal/catch-up/refresh tasks use `except Exception: pass`. | Calendar drift, expired subscriptions, and suggestion gaps can persist invisibly. |
| Theming | React Native | Feature screens define local palettes instead of consuming the shared theme module. | Styling drift is already underway and future global theme changes will be expensive. |

### Logical & Silent Fail Report

- ✅ Fixed — Level 1: CSRF enforcement restored on cookie-authenticated web APIs.
  - Fix: removed the `enforce_csrf` override from `CsrfExemptSessionAuthentication` in `views.py` so `SessionAuthentication.enforce_csrf()` runs normally for session-based requests. Added a Vue axios request interceptor in `frontend/src/services/api.ts` that reads the `csrftoken` cookie (set by Django on login) and forwards it as `X-CSRFToken` on all state-mutating requests (POST/PUT/PATCH/DELETE).

- ✅ Fixed — Level 1: mobile photo-proof upload field name corrected.
  - Fix: `TaskDetailScreen.tsx` line 475 changed `formData.append('photo_proof', ...)` to `formData.append('photo', ...)` to match the backend's `request.FILES.get('photo')`. The `taskService.ts` comment already documented the correct field name.

- ✅ Fixed — Level 2: task-template creation now surfaces occurrence generation failure to callers.
  - Fix: `task_template_router.py` now sets `generation_warning` in the 201 response body when occurrence generation throws, so future UI can detect and display the partial-failure message. The exception is still logged via `logger.exception`. Occurrence generation failure never causes a 500 (the template is saved and valid); the warning tells callers to expect a delay until the nightly job runs.

- ✅ Fixed — Level 2: background sync/suggestion jobs now log all failures.
  - Fix: all six `except Exception: pass` blocks in `tasks.py` replaced with `logger.exception(...)` calls that include `calendar_id` and `user_id` context. Failed-item counts are included in task return values. Jobs continue processing remaining items after a single failure (batch-resilient, not abort-on-error).
  - Affected tasks: `renew_google_watch_channels`, `catchup_google_calendar_sync`, `renew_outlook_subscriptions`, `refresh_outlook_tokens`, `generate_smart_suggestions`, `catchup_outlook_calendar_sync`.

### Non-Functional / Incomplete Features

- Photo-proof upload is implemented in mobile UI but is not functional because of the multipart mismatch.
- Task-template creation is not reliably end to end because success does not guarantee initial occurrence materialization.
- Previously reported orphan flows remain unresolved after re-verification:
  - `accept-emergency` is still only present in service wrappers, with no screen-level usage found in either frontend.
  - Group stats, assignment matrix, and notification history remain declared but unrendered in actual UI flows.

### Backend Integrity Report

- Auth boundary weakness:
  - The backend currently mixes browser session auth with CSRF-exempt API views instead of using either protected session flows or a fully tokenized web client.

- Data-flow integrity weakness:
  - `TaskTemplate -> occurrence generation -> task board` is not atomic. Template persistence can succeed while the user-visible task layer fails to materialize.

- Quality assurance gap:
  - Critical test files such as [`backend/chore_sync/tests/test_auth_service.py#L9`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/tests/test_auth_service.py#L9), [`backend/chore_sync/tests/test_task_lifecycle_service.py#L9`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/tests/test_task_lifecycle_service.py#L9), and [`backend/chore_sync/tests/test_notification_service.py#L9`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/tests/test_notification_service.py#L9) are still placeholder `pytest.skip(...)` files, which helps explain why silent runtime failures keep surviving.

### The Zombie List

- Misleading live contract:
  - [`mobile/src/services/taskService.ts#L37`](/home/mahamad/Projects/ChoreSync/mobile/src/services/taskService.ts#L37) documents the correct upload contract, but the only real caller violates it. The comment is accurate; the runtime path is not.

- Still-orphaned wrappers re-verified:
  - [`frontend/src/services/api.ts#L26`](/home/mahamad/Projects/ChoreSync/frontend/src/services/api.ts#L26) `groupApi.stats`
  - [`frontend/src/services/api.ts#L51`](/home/mahamad/Projects/ChoreSync/frontend/src/services/api.ts#L51) `taskApi.acceptEmergency`
  - [`frontend/src/services/api.ts#L73`](/home/mahamad/Projects/ChoreSync/frontend/src/services/api.ts#L73) `notificationApi.history`
  - [`mobile/src/services/taskService.ts#L25`](/home/mahamad/Projects/ChoreSync/mobile/src/services/taskService.ts#L25) `acceptEmergency`

### Documentation Redline

- Incorrect status in the existing audit:
  - Existing file says mobile photo-proof upload UI is absent.
  - Corrected version: the UI exists now, but it submits the wrong field name and fails at runtime.

- Incorrect operational comment:
  - Current code comment in [`backend/chore_sync/tasks.py#L418`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/tasks.py#L418) says `pass  # log but don't abort the whole run`.
  - Corrected version: `logger.exception(...); continue  # preserve batch progress while recording the failure`.

### Styling Drift

- React Native feature screens are bypassing the shared theme module with local hardcoded token maps.
  - Examples: [`mobile/src/screens/calendar/CalendarScreen.tsx#L28`](/home/mahamad/Projects/ChoreSync/mobile/src/screens/calendar/CalendarScreen.tsx#L28) and [`mobile/src/screens/groups/GroupsScreen.tsx#L34`](/home/mahamad/Projects/ChoreSync/mobile/src/screens/groups/GroupsScreen.tsx#L34).
  - Impact: `mobile/src/theme/colors.ts`, `mobile/src/theme/index.ts`, and `mobile/src/theme/typography.ts` exist, but important screens are drifting away from them, which will slow down future theming and produce inconsistent UI behavior.

---

## Fix Pass Summary (2026-04-04 — Pass 2)

### Issues fixed in this pass

| Issue | Severity | Files Changed |
|-------|----------|--------------|
| Mobile photo-proof upload used wrong field name `photo_proof` (backend requires `photo`) | Level 1 | `mobile/src/screens/tasks/TaskDetailScreen.tsx` |
| CSRF enforcement disabled on all session-authenticated API endpoints | Level 1 | `backend/chore_sync/api/views.py` (restored `enforce_csrf`), `frontend/src/services/api.ts` (added `X-CSRFToken` interceptor) |
| Task-template creation returned HTTP 201 with no indication when initial occurrence generation failed | Level 2 | `backend/chore_sync/api/task_template_router.py` (added `generation_warning` field) |
| Six background Celery jobs swallowed all exceptions silently (no log, no visibility) | Level 2 | `backend/chore_sync/tasks.py` (`renew_google_watch_channels`, `catchup_google_calendar_sync`, `renew_outlook_subscriptions`, `refresh_outlook_tokens`, `generate_smart_suggestions`, `catchup_outlook_calendar_sync`) |
| Mobile `handleMarkRead` applied optimistic state update with no rollback on API failure | Level 2 | `mobile/src/stores/notificationStore.ts` (added `markUnread`), `mobile/src/screens/notifications/NotificationsScreen.tsx` |
| Mobile `handleSwapDecline` dismissed notification from store even when backend API call failed | Level 2 | `mobile/src/screens/notifications/NotificationsScreen.tsx` |
| `useAppForegroundRefresh` hook was never mounted — foreground refresh did nothing | Level 2 | `mobile/src/screens/home/HomeScreen.tsx` |
| Badge data not surfaced in React Native despite `/api/users/me/badges/` existing | Feature gap | `mobile/src/screens/profile/ProfileScreen.tsx` (added Achievements section + badge detail modal) |
| Vue badge chips not interactive — no date/time/points detail view | Feature gap | `frontend/src/views/UpdateProfileView.vue`, `backend/chore_sync/services/insights_service.py` (added `emoji` field) |

### Issues verified as already resolved (pre-existing from last pass)

- All items in the 2026-04-04 Pass 1 summary remain resolved.

### Issues still unresolved

| Issue | Reason |
|-------|--------|
| Vue web chat send gives no error if socket closed | Minor; web socket is reliably reconnected; deferred |
| Mobile `?tab=chat` not passed through cross-stack navigation | React Navigation cross-stack param passing is non-trivial; deferred |
| Mobile task authoring (no create/edit screen) | Full feature screen required; deferred |
| Emergency reassign accept UI (no screen in either frontend) | Full feature screen required; deferred |
| Outlook writeback (`is_task_writeback`) missing from Vue web calendar selection | Vue calendar select form update needed; deferred |
| Group analytics screens (`/api/groups/<uuid>/stats/`, assignment-matrix) | UI feature work; deferred |
| Sync reliability / conflict handling across providers | Architectural task; deferred |
| React Native screens use local palette constants instead of shared theme tokens | Cosmetic/architectural drift; deferred |
| Vue chart + calendar affordance hardcoded colors | Cosmetic; deferred |
