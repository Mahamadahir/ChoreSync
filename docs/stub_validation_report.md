# Stub Validation Report

## Executive Summary

Validated 16 stub service files and 3 provider files against `implementation_guide.md`. **13 services are intentional scaffolding**, **4 services are orphaned** (not in guide), and **4 calendar-related stubs are redundant** (duplicated by implemented `google_calendar_service.py`).

---

## Validated Services (Intentional Scaffolding - Keep)

| File | Class | Guide Reference | Verdict |
|------|-------|-----------------|---------|
| services/task_service.py | TaskScheduler | Step 6 | ✅ KEEP — matches guide interface |
| services/task_lifecycle_service.py | TaskLifecycleService | Steps 6, 8 | ✅ KEEP — matches guide interface |
| services/task_template_service.py | TaskTemplateService | Step 5 | ✅ KEEP — matches guide interface |
| services/group_service.py | GroupOrchestrator | Step 4 | ✅ KEEP — matches guide interface |
| services/notification_service.py | NotificationService | Step 10 | ✅ KEEP — matches guide interface |
| services/proposal_service.py | ProposalService | Step 11 | ✅ KEEP — matches guide interface |
| services/messaging_service.py | MessagingService | Step 10 (chat) | ✅ KEEP — matches guide interface |
| services/insights_service.py | InsightsService | Step 12 | ✅ KEEP — matches guide interface |
| services/membership_service.py | MembershipService | Step 4 (group membership ops) | ✅ KEEP — matches guide interface |
| sync_providers/google_provider.py | GoogleCalendarProvider | OAuth sync (mentioned) | ✅ KEEP — provider pattern for future Step |
| sync_providers/apple_provider.py | AppleCalendarProvider | OAuth sync (mentioned as pending) | ✅ KEEP — provider pattern for future Step |
| sync_providers/outlook_provider.py | OutlookCalendarProvider | OAuth sync (mentioned as pending) | ✅ KEEP — provider pattern for future Step |

### Verification Details

**All verified services:**
- ✅ Class names match guide specifications
- ✅ Method signatures align with guide's intended interfaces
- ✅ TODOs reference correct implementation step numbers
- ✅ No duplicate logic found in views.py, models.py, or serializers.py

---

## Orphaned Services (Not in Guide - Recommend Delete)

| File | Class | Issue | Recommended Action |
|------|-------|-------|-------------------|
| services/nudge_service.py | SmartNudgeService | Not mentioned in implementation_guide.md; no corresponding model or step | DELETE — out of scope |
| services/guest_access_service.py | GuestAccessService | Not mentioned in implementation_guide.md; no corresponding model or step | DELETE — out of scope |
| services/playbook_service.py | PlaybookService | Not mentioned in implementation_guide.md; no corresponding model or step | DELETE — out of scope |
| services/inventory_service.py | InventoryService | Not mentioned in implementation_guide.md; no corresponding model or step | DELETE — out of scope |

### Analysis

These four services introduce features **not specified in `choresync_project_plan.md` or `implementation_guide.md`**:
- **SmartNudgeService**: adaptive reminder engine — no corresponding models or requirements
- **GuestAccessService**: temporary visitor access — no GuestInvite model exists
- **PlaybookService**: multi-step routine templates — no Playbook model exists
- **InventoryService**: shopping list sync — no InventoryItem or ShoppingList models exist

None of these services are imported in `views.py`, and all methods raise `NotImplementedError`. They represent **scope creep** beyond the defined MVP.

---

## Redundant Calendar Services (Duplicated Logic)

| File | Class | Status | Issue |
|------|-------|--------|-------|
| services/calendar_service.py | CalendarSyncService | STUB (all methods raise NotImplementedError) | Redundant with google_calendar_service.py |
| services/calendar_event_service.py | CalendarEventService | STUB (all methods raise NotImplementedError) | Redundant with google_calendar_service.py |
| services/calendar_auth_service.py | CalendarAuthService | STUB (all methods raise NotImplementedError) | Redundant with google_calendar_service.py |
| services/google_calendar_service.py | GoogleCalendarService | **FULLY IMPLEMENTED** ✅ | **ACTIVE** — imported in views.py |

### Duplication Analysis

**google_calendar_service.py** (399 lines) is a **fully implemented** service that:
- ✅ Implements OAuth flow (`build_auth_url`, `exchange_code`)
- ✅ Manages credential refresh and storage
- ✅ Implements bidirectional sync (`pull_events`, `push_event`)
- ✅ Handles conflict resolution (ETag matching)
- ✅ Actively used by `GoogleCalendarAuthURLAPIView`, `GoogleCalendarCallbackAPIView`, `GoogleCalendarSyncAPIView`

**Stub services duplicating this logic:**
- `calendar_auth_service.py` → methods like `store_credentials`, `refresh_access_token` are already in `google_calendar_service.py`
- `calendar_event_service.py` → methods like `create_event`, `update_event` are already in `google_calendar_service.py`
- `calendar_service.py` → methods like `sync_google_calendar`, `pull_events_from_google` are already in `google_calendar_service.py`

### Recommended Action

**DELETE** all three stub calendar services:
1. `services/calendar_service.py` (CalendarSyncService)
2. `services/calendar_event_service.py` (CalendarEventService)
3. `services/calendar_auth_service.py` (CalendarAuthService)

**Rationale:** The guide's Step 3 references token encryption (implemented in `google_calendar_service.py`), not separate service stubs. The provider pattern (`google_provider.py`, `apple_provider.py`, `outlook_provider.py`) is the correct abstraction for multi-provider sync, not parallel service files.

---

## Implemented Services (Not Stubs)

| File | Class | Status |
|------|-------|--------|
| services/auth_service.py | AccountService | ✅ FULLY IMPLEMENTED (register, login, verification, password reset, OAuth) |
| services/google_calendar_service.py | GoogleCalendarService | ✅ FULLY IMPLEMENTED (OAuth, sync, conflict resolution) |

Both are actively used in `views.py` and match their respective guide requirements.

---

## Summary Statistics

- **Intentional scaffolding (keep):** 12 services + 3 providers = 15 files
- **Orphaned (delete):** 4 services
- **Redundant (delete):** 3 calendar stub services
- **Implemented (keep):** 2 services

**Total files to delete:** 7
**Total stub files to keep:** 15

---

## Recommended Deletions (Combined with Dead Code Audit)

### Backend Dead Code (from previous audit)
1. `backend/chore_sync/apps.py` — FastAPI app never used
2. `backend/chore_sync/api/task_router.py` — FastAPI dead code
3. `backend/chore_sync/api/group_router.py` — FastAPI dead code
4. `backend/chore_sync/api/auth_router.py` — FastAPI dead code
5. `backend/chore_sync/api/calendar_router.py` — FastAPI dead code
6. `backend/chore_sync/tests/test_task_router.py`
7. `backend/chore_sync/tests/test_group_router.py`
8. `backend/chore_sync/tests/test_calendar_router.py`
9. `backend/chore_sync/repositories/` — empty directory

### Backend Orphaned Services (new findings)
10. `backend/chore_sync/services/nudge_service.py`
11. `backend/chore_sync/services/guest_access_service.py`
12. `backend/chore_sync/services/playbook_service.py`
13. `backend/chore_sync/services/inventory_service.py`

### Backend Redundant Calendar Stubs (new findings)
14. `backend/chore_sync/services/calendar_service.py`
15. `backend/chore_sync/services/calendar_event_service.py`
16. `backend/chore_sync/services/calendar_auth_service.py`

### Backend Orphaned Tests (new findings)
17. `backend/chore_sync/tests/test_guest_access_service.py`
18. `backend/chore_sync/tests/test_inventory_service.py`
19. `backend/chore_sync/tests/test_nudge_service.py`
20. `backend/chore_sync/tests/test_playbook_service.py`
21. `backend/chore_sync/tests/test_calendar_service.py`
22. `backend/chore_sync/tests/test_calendar_event_service.py`
23. `backend/chore_sync/tests/test_calendar_auth_service.py`

### Frontend Dead Code (from previous audit)
24. `frontend/src/controllers/` — entire directory (12 files)
25. `frontend/src/components/TaskBoard.ts`
26. `frontend/src/components/MessagePanel.ts`
27. `frontend/src/components/CalendarSyncPanel.ts`
28. `frontend/src/services/AuthGateway.ts`
29. `frontend/src/services/NotificationSocketService.ts`
30. `frontend/src/composables/useAuth.ts`

### Dependency Cleanup
31. Remove `fastapi` and `uvicorn` from `backend/pyproject.toml`
32. Remove imports of `useAuth` from `frontend/src/views/{GoogleLoginView,MicrosoftLoginView,HomeView,LoginView}.vue`

**Total items to delete:** 32 files/directories + 2 dependency updates

---

## Implementation Guide Update Required

The following sections need updates:

1. **Step 1 (Fix Architecture)** — add deletion of orphaned services to cleanup tasks
2. **Critical Architectural Problems** — add note about calendar service duplication
3. **Gap Table** — update calendar sync rows to reflect google_calendar_service.py implementation status
