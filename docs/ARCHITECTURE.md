# ChoreSync — Architecture Overview

This is a public overview of how ChoreSync is built. It covers the design and the
parts I found interesting to solve. It deliberately stays at the level of how the
system works rather than shipping the source, which is private.

## System overview

ChoreSync coordinates recurring household chores across a group. Members create task
templates with recurrence rules; the backend generates each occurrence and assigns it
to the fairest available member using a multi-stage scoring pipeline. Members complete,
snooze, swap, or auction tasks; they earn points, streaks and badges; and the household
chats and votes on changes in real time.

```
  Vue 3 web app  ──  REST (session + CSRF)  ──┐
                     WebSocket / SSE          │
                                              ├──  Django + DRF (ASGI / Daphne)  ──  PostgreSQL
  Expo mobile app  ──  REST (JWT)  ───────────┤    Channels consumer + SSE
                       WebSocket + push       │    Celery worker + beat       ──  Redis
                                              ┘
                                   Gemini API   ·   Google / Microsoft Graph
```

Two clients (web and mobile) hit one REST API. The backend runs under Daphne, so a
single process serves HTTP, WebSockets and SSE. Celery handles all scheduled and
deferred work. Redis is both the Celery broker and the Channels message bus. PostgreSQL
is the store.

## Backend design

The backend is layered: URL to view to service to model. Views stay thin and handle
auth, validation and serialisation; the business logic lives in a service layer. Models,
tasks and admin are each split into packages by domain rather than living in single
large modules.

Both session auth (for the web app) and JWT auth (for mobile) are enabled at once, so
the same API serves both clients without duplication.

## The assignment algorithm

Each candidate gets a score and the lowest score wins. The full breakdown is persisted
and exposed through the API, so the app can always explain why someone was chosen.

1. **Normalised fairness (0–1).** Four sub-scores from work already done: task count,
   estimated time, points, and a cognitive-load measure that includes invisible work
   like creating templates, proposing changes and voting.
2. **Explicit preference.** A prefer or avoid marking on a chore multiplies the score
   down or up.
3. **Implicit affinity.** With no explicit preference, history fills the gap. A high
   completion rate on a chore is read as an implicit preference; repeatedly swapping a
   chore away is read as an implicit dislike.
4. **Calendar availability.** Busy time over the task window adds a penalty. The penalty
   is additive and capped, so a busy calendar shifts the decision but never overrides
   fairness entirely.

Ties break by least-recently-assigned, then by who joined the household first.

## Calendar sync and availability

Two providers, Google Calendar and Microsoft Outlook, write into one provider-agnostic
event store. The assignment pipeline reads availability from that store with no
provider-specific branches, which is what makes adding a third provider a small change.

The initial Google sync pulls two years of events in monthly chunks, advancing a
checkpoint after each chunk so a rate-limit response resumes rather than restarts. Live
webhooks are paused during the backfill so they don't race the bulk pull. Outlook uses
Graph's delta cursor for the same incremental behaviour. A set of periodic safety-net
jobs renews watch channels and subscriptions and runs catch-up syncs, because push
webhooks alone can't be trusted to never miss an event.

OAuth tokens are encrypted at rest with Fernet field encryption.

## Background jobs

Celery runs every scheduled and deferred job: generating daily occurrences, dispatching
deadline reminders, marking tasks overdue, recalculating the leaderboard, renewing
calendar subscriptions, purging deleted accounts after their grace period, and more.
Initial calendar syncs route to a dedicated queue so a long backfill can't block
time-sensitive reminders. Exactly one beat scheduler runs; a second would double-fire
every job.

## Real-time layer

One notification call fans out over three paths: WebSocket for lowest latency, SSE for
graceful browser reconnect, and Expo push to reach a backgrounded phone. The
notification is written to the database first, then pushed, so a brief disconnect
replays missed messages on reconnect rather than dropping them. Household chat, read
receipts and ephemeral UI updates all travel over the same socket.

## AI assistant

A conversational assistant built on Google Gemini, reached only through the ChoreSync
API. It uses function calling: Gemini fills in the arguments, the backend dispatches to
a handler and runs the real action, and handler errors come back as plain text rather
than HTTP errors. The system prompt is rebuilt each turn with the current time so
relative phrases resolve, and it gates destructive actions behind confirmation. Personal
data such as emails and tokens is stripped before anything is sent to Gemini.

A separate, rule-based suggestion engine runs daily and nudges people about habitual
chores, free calendar slots, preferred-but-unassigned tasks, and uneven workloads.

## Deployment

ChoreSync runs on Azure Container Apps. One backend image is reused by the web,
worker and beat apps; the frontend is a separate static build on Azure Static Web Apps.
The web and mobile clients are split across two domains, with the CSRF cookie scoped to
the parent domain so the frontend origin can read it. GitHub Actions runs the tests,
builds the image and rolls out the apps on each push. Cloudflare sits in front for DNS.
The stack was migrated here from a university OpenShift cluster; see MIGRATION.md in the
main repository for the move.

On the operations side, Postgres is a managed Flexible Server with automated
point-in-time backups, media lives in Blob storage so the web tier stays stateless,
a deep health check reports the database and broker rather than just returning 200, and
an external dead-man's-switch heartbeat catches a silently failed background worker even
during a full outage.
