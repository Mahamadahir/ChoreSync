# Mobile Forensic Audit

Date: 2026-04-12

## Executive Summary
Mobile-to-backend maturity is solid for core CRUD flows, but parity with the Vue app is still incomplete in the places where the web client maintains long-lived or timezone-aware data bridges. The two highest-risk gaps are:

1. Mobile still has no global real-time notification/replay bridge equivalent to the web socket client, so in-app notification freshness depends on push delivery, app resume, or manual refresh.
2. Mobile calendar create/edit/day-grouping logic serializes local times incorrectly and reads server datetimes naively, which can shift events to the wrong hour or day outside UTC.

The backend itself is largely ready. Most remaining problems are not missing Django routes; they are client wiring gaps where the mobile app either never connects to an existing endpoint or transforms the payload differently from the web app.

## Existing Issues Review (2026-04-12 Review of Prior Audit)
- ✅ Resolved: AI assistant chat history replay works. `mobile/src/screens/assistant/AssistantScreen.tsx:157-194` loads `/api/assistant/sessions/` and `/api/assistant/?session_id=...`.
- ✅ Resolved: Profile email updates work via `POST /api/profile/`. `mobile/src/screens/profile/ProfileScreen.tsx:293-307`
- ✅ Resolved: Profile password updates use the correct backend contract. `mobile/src/screens/profile/ProfileScreen.tsx:309-333`
- ✅ Resolved: Notification preferences route to a real editor screen backed by `GET/PATCH /api/users/me/notification-preferences/`. `mobile/src/screens/notifications/NotificationPreferencesScreen.tsx:205-243`
- ✅ Resolved: Group detail payload exposes `my_role` and `member_count`. `backend/chore_sync/api/group_router.py:121-132`
- ✅ Resolved: Group members payload exposes `first_name` and `last_name`. `backend/chore_sync/api/group_router.py:175-181`
- ✅ Resolved: Proposal notifications deep-link to the dedicated proposals screen. `mobile/src/screens/notifications/NotificationsScreen.tsx:336-343`
- ✅ Resolved: Notification badge bootstraps on initial mount. `mobile/src/components/common/AppHeader.tsx:27-39`
- ✅ Resolved: Mobile tasks load pending swaps. `mobile/src/screens/tasks/TasksScreen.tsx:355-363`
- ✅ Resolved: Profile calendar toggles route the user into the calendar flow. `mobile/src/screens/profile/ProfileScreen.tsx:275-290`
- ✅ Resolved: Push-token backend readiness is closed. `backend/chore_sync/api/notification_router.py:153-179` and `mobile/src/services/notificationService.ts:18-23`
- ✅ Resolved: `HomeScreen` no longer fails completely silently; it now alerts on partial failures. `mobile/src/screens/home/HomeScreen.tsx:170-218`
- ✅ Resolved: `ProfileScreen` no longer swallows stats/badge failures into fake empty states; it surfaces retry UI. `mobile/src/screens/profile/ProfileScreen.tsx:158-196` and `mobile/src/screens/profile/ProfileScreen.tsx:399-405`
- ❌ Still Present: Mobile does not consume `GET /api/events/stream/`. `backend/chore_sync/urls.py:163`, `frontend/src/services/eventService.ts:46-50`

## The "Feature Parity" Table
| Feature (Vue) | Status in Mobile | Missing Logic/Wiring | Severity |
| :--- | :--- | :--- | :--- |
| Global real-time notifications with replay | Missing | Web connects a replay-aware `NotificationSocketService` app-wide; mobile only does mount-time REST bootstrap, foreground refresh, and Expo push handling. No mobile client opens the personal notification socket bridge. | Level 1 |
| Calendar create/edit with correct local-time handling | Broken | Mobile builds UTC timestamps by string concatenation and reads ISO datetimes by string slicing, unlike the web client’s local `Date -> toISOString()` flow. This can shift event times and day buckets. | Level 1 |
| Calendar source filtering, combine mode, and SSE refresh | Partial | Web calendar uses `/api/events/stream/` plus per-calendar filtering and combine mode; mobile only loads `/api/events/` windows and refreshes on sync notifications. | Level 2 |
| Profile calendar connection status summary | Broken | The mobile Profile screen renders Google/Outlook toggles from local booleans instead of hydrating them from `/api/calendar/status/`. The UI looks connected/disconnected, but it is not backend-backed. | Level 2 |
| Profile analytics depth | Partial | Web profile includes richer progress charts; mobile only exposes summary stats and badges. The backend data exists, but the mobile view stops at the summary layer. | Level 3 |

## Broken Bridges (Data Flow Issues)
- **Level 1: The web’s global notification bridge is unwired on mobile.**
  Backend real-time notification delivery and replay exist in `backend/chore_sync/django_app/consumers.py:25-74` and `backend/chore_sync/django_app/consumers.py:130-138`. The web app connects that bridge globally through `frontend/src/App.vue:161-172` and `frontend/src/App.vue:309-339`, using reconnect/replay support from `frontend/src/services/NotificationSocketService.ts:75-170`. Mobile, by contrast, only hydrates notifications via `mobile/src/components/common/AppHeader.tsx:30-39`, foreground polling in `mobile/src/hooks/useAppForegroundRefresh.ts:17-35`, and push listeners in `mobile/src/hooks/usePushNotifications.ts:76-106`. There is no mobile service or hook that opens the personal `/ws/chores/` notification socket with replay state. Result: notifications generated while the app is open can remain stale unless a push arrives or the app is resumed.

- **Level 1: Calendar event timestamps are transformed incorrectly on mobile.**
  The mobile calendar creates UTC timestamps with `buildIso()` by appending `Z` directly in `mobile/src/screens/calendar/CalendarScreen.tsx:359-361`, reads server datetimes with `isoToHHMM()` using raw string slicing in `mobile/src/screens/calendar/CalendarScreen.tsx:346-350`, groups events by `ev.start.split('T')[0]` in `mobile/src/screens/calendar/CalendarScreen.tsx:417-430` and `mobile/src/screens/calendar/CalendarScreen.tsx:452`, and reuses `editEvent.start.split('T')[0]` when saving edits in `mobile/src/screens/calendar/CalendarScreen.tsx:508-517`. The web flow uses local `Date` conversion before `toISOString()` in `frontend/src/views/CalendarView.vue:337-350`. Result: on non-UTC devices, mobile can create, edit, and render events at the wrong local time or on the wrong day.

- **Level 2: The mobile calendar stops at REST and never attaches to the backend live-update stream.**
  Django exposes `GET /api/events/stream/` in `backend/chore_sync/urls.py:163` and the web client consumes it through `frontend/src/services/eventService.ts:46-50`, then starts the stream in `frontend/src/views/CalendarView.vue:268-280`. Mobile only fetches `/api/events/` in `mobile/src/screens/calendar/CalendarScreen.tsx:401-435` and reloads when a `calendar_sync_complete` notification appears in `mobile/src/screens/calendar/CalendarScreen.tsx:440-450`. The data exists server-side, but the mobile app never subscribes to the live bridge.

- **Level 2: The Profile screen’s calendar status card is visually present but not API-backed.**
  The backend exposes real connection state through `backend/chore_sync/api/views.py:1021-1045`, and the mobile Calendar screen uses it correctly in `mobile/src/screens/calendar/CalendarScreen.tsx:936-943`. The Profile screen, however, keeps `googleConnected` and `outlookConnected` as local state only in `mobile/src/screens/profile/ProfileScreen.tsx:113-115`, renders those flags in `mobile/src/screens/profile/ProfileScreen.tsx:490-514`, and changes them via navigation-only toggle handlers in `mobile/src/screens/profile/ProfileScreen.tsx:275-290`. Result: the profile UI can show a disconnected state even when the backend is connected, or vice versa.

## Silent Fail / Contract Risk Notes
- `mobile/src/screens/groups/GroupDetailScreen.tsx:341-355` still uses `Promise.allSettled()` for the main group payload and never surfaces which panel failed. The screen can quietly degrade into partially missing tabs.
- `mobile/src/screens/assistant/AssistantScreen.tsx:175-194` treats failed session reload as non-critical and silently drops history restoration, which can make backend/API failures look like an empty thread.
- `mobile/src/screens/calendar/CalendarScreen.tsx:393-399` swallows `/api/calendars/` load failures, so event creation may degrade without a visible explanation when no calendar choices appear.

## Backend Integrity Report
### Exposed by backend and used by web, but still missing or incomplete in mobile
- `GET /api/events/stream/` exists at `backend/chore_sync/urls.py:163` and is used by the web client via `frontend/src/services/eventService.ts:46-50`, but has no mobile consumer.
- The personal notification replay path over `/ws/chores/` exists in `backend/chore_sync/django_app/consumers.py:54-74`, and the web client uses it through `frontend/src/services/NotificationSocketService.ts:131-169`, but mobile never opens that bridge for notifications.
- `GET /api/calendar/status/` exists and is used on the mobile Calendar screen, but the same backend truth is not wired into the Profile screen’s “Connected Calendars” UI.

### Backend/mobile contract mismatches
- Mobile calendar event save logic treats local times as already-UTC strings. `mobile/src/screens/calendar/CalendarScreen.tsx:359-361`
- Mobile calendar edit/day-bucketing logic parses ISO datetimes by string splitting instead of converting them to local `Date` instances first. `mobile/src/screens/calendar/CalendarScreen.tsx:346-350`, `mobile/src/screens/calendar/CalendarScreen.tsx:417-430`, `mobile/src/screens/calendar/CalendarScreen.tsx:452`

### Mobile-specific API readiness
- I did not find a backend model needed for current mobile features that is present in the database but still unexposed.
- `UserPushToken` and `/api/push-token/` are properly exposed and wired. `backend/chore_sync/api/notification_router.py:153-179`, `mobile/src/services/notificationService.ts:18-23`

### Unused or weakly used endpoints
- `GET /api/notifications/history/` has a mobile service wrapper in `mobile/src/services/notificationService.ts:6-7`, but I did not find a caller in `/mobile`.
- `POST /api/auth/token/verify/` is exposed in `backend/chore_sync/urls.py:129`, but I did not find a mobile caller.

## The Zombie List
- `mobile/src/services/notificationService.ts:6-7` exposes `history()` with no mobile caller.
- `mobile/src/services/authService.ts:11-12` exposes `refreshToken()`, but token refresh is handled directly in the Axios interceptor instead of through this wrapper. `mobile/src/services/api.ts:45-56`
- `mobile/src/screens/profile/ProfileScreen.tsx:490-514` contains a calendar-status summary card that looks live but is driven by local booleans instead of backend state.

## New Issues (Latest Audit - 2026-04-12)
- **Level 1: Global real-time notifications and replay are still unwired on mobile.**
  This is the clearest web-to-mobile broken bridge still remaining. The backend and web client both support replayable real-time notifications, but mobile does not attach to that channel at all.

- **Level 1: Mobile calendar event times can drift because the client serializes local times as UTC.**
  This is a backend contract mismatch rather than a missing route. It is likely to produce “wrong hour” and “wrong day” bugs in real use, especially outside UTC.

- **Level 2: Mobile never consumes `/api/events/stream/`, so calendar freshness depends on sync notifications or manual refresh.**

- **Level 2: The Profile screen’s “Connected Calendars” status is still a local placeholder rather than a backend-backed summary.**
