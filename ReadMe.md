;# ChoreSync

Household chore coordination platform — smart assignment, gamification, real-time chat, and two-way calendar sync.

**Stack:** Django 5 + Django Channels (Daphne ASGI) · DRF · Celery + Redis · PostgreSQL · Vue 3 + Quasar (Vite)

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| Node.js | 20+ | |
| PostgreSQL | 14+ | database |
| Redis | 7+ | Celery broker + result backend |

Create the Postgres database before first run:
```sql
CREATE USER choresync_user WITH PASSWORD 'choreSync';
CREATE DATABASE choresync OWNER choresync_user;
```

---

## 1 · Backend

### Setup (once)

```bash
# From repo root
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

pip install -r requirements.txt

cd backend
python manage.py migrate
python manage.py collectstatic --noinput   # required for admin styles under Daphne
python seed_badges.py              # seeds the 26 default badges
python manage.py createsuperuser   # optional
```

Copy `backend/secrets.env` and fill in your values (it is already loaded by `settings.py`):

```env
SECRET_KEY=...
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://choresync_user:choreSync@localhost:5432/choresync
FIELD_ENCRYPTION_KEY=...           # generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

FRONTEND_APP_URL=http://localhost:5173
FRONTEND_VERIFY_EMAIL_URL=http://localhost:5173/verify-email
FRONTEND_RESET_PASSWORD_URL=http://localhost:5173/reset-password
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Email (Gmail app password works)
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx

# Google Calendar OAuth (optional)
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/calendar/google/callback/

# Microsoft / Outlook OAuth (optional)
MICROSOFT_CLIENT_ID=
MICROSOFT_TENANT_ID=common
MICROSOFT_CLIENT_SECRET=
OUTLOOK_OAUTH_REDIRECT_URI=http://localhost:8000/api/calendar/outlook/callback/
BACKEND_BASE_URL=http://localhost:8000
OUTLOOK_WEBHOOK_SECRET=
```

### Start the backend server

The backend uses **Daphne** (ASGI) to support WebSockets. Use it instead of `runserver`:

```bash
cd backend
daphne -b 0.0.0.0 -p 8000 chore_sync.asgi:application
```

> `python manage.py runserver` still works for HTTP-only development but WebSocket features (real-time chat, live notifications) will not function.

---

## 2 · Frontend

### Setup (once)

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=<your-google-client-id>
VITE_MSAL_CLIENT_ID=<your-azure-app-client-id>
VITE_MSAL_AUTHORITY=https://login.microsoftonline.com/common
```

### Start the dev server

```bash
cd frontend
npm run dev
# → http://localhost:5173
```

---

## 3 · Celery Workers

Celery powers recurring task generation, deadline reminders, leaderboard updates, badge evaluation, and calendar syncs. **Redis must be running** before starting workers.

Three processes are needed in total. Run each in a separate terminal from the **`backend/`** directory with the venv active.

### Terminal A — default worker (all general tasks)

```bash
cd backend
celery -A chore_sync worker -Q default --concurrency=4 -l info
```

Handles: recurring task generation · deadline reminders · overdue marking · swap cleanup · leaderboard recalculation · badge evaluation · smart suggestions · marketplace cleanup.

### Terminal B — calendar sync worker (long-running syncs)

```bash
cd backend
celery -A chore_sync worker -Q calendar_sync --concurrency=3 -l info
```

Handles: initial Google/Outlook calendar syncs (chunked, crash-resumable) · watch channel renewal · catchup syncs when webhooks expire.

> Kept separate so a slow 10,000-event initial sync doesn't block deadline reminders on the default queue.

### Terminal C — beat scheduler (triggers periodic tasks)

```bash
cd backend
celery -A chore_sync beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Drives all time-based triggers:

| Schedule | Task |
|---|---|
| Daily midnight | Generate recurring task occurrences (7-day horizon) |
| Every 15 min | Dispatch deadline reminders (24 h, 3 h, at-due windows) |
| Every 15 min | Mark overdue tasks |
| Daily 02:00 | Clean up expired task swaps |
| Hourly | Recalculate leaderboard / UserStats |
| Daily 08:00 | Generate smart suggestions |
| Daily 03:00 | Renew Google Calendar watch channels |
| Every 6 h | Catchup Google sync (for expired watch channels) |
| Every 2 h | Renew Outlook Graph webhook subscriptions |

> Only **one** beat process should run at a time.

---

## 4 · All processes at a glance

```
Terminal 1   daphne -b 0.0.0.0 -p 8000 chore_sync.asgi:application   (backend)
Terminal 2   npm run dev                                                (frontend)
Terminal 3   celery -A chore_sync worker -Q default --concurrency=4   (worker — general)
Terminal 4   celery -A chore_sync worker -Q calendar_sync --concurrency=3  (worker — calendar)
Terminal 5   celery -A chore_sync beat --scheduler django_celery_beat.schedulers:DatabaseScheduler  (scheduler)
```

---

## 5 · Remote / tunnel testing (Google & Outlook OAuth, webhooks)

Google Calendar webhooks and Outlook Graph subscriptions require a **publicly accessible HTTPS URL**. Use a Cloudflare tunnel for local dev:

```bash
cloudflared tunnel --url http://localhost:8000
```

Once you have the public URL, update `secrets.env`:
```env
BACKEND_BASE_URL=https://xxxx.trycloudflare.com
GOOGLE_OAUTH_REDIRECT_URI=https://xxxx.trycloudflare.com/api/calendar/google/callback/
OUTLOOK_OAUTH_REDIRECT_URI=https://xxxx.trycloudflare.com/api/calendar/outlook/callback/
```

Also update the redirect URIs in your Google Cloud Console and Azure App Registration to match.

The PowerShell helper script `scripts/start_dev_all.ps1` launches backend + frontend + two tunnels in Windows Terminal tabs and optionally auto-patches `secrets.env` and `frontend/.env.local` with the tunnel URLs.

---

## 6 · Running tests

```bash
cd backend
python manage.py check
python -m pytest
```

---

## Features

- **Auth:** signup · login · logout · email verification · password reset · profile update · timezone stored per user
- **Social login:** Google & Microsoft (ID token verification on backend)
- **Groups:** create/join by code · invite by email · moderator/member roles · leave group
- **Tasks:** templates with recurrence (daily/weekly/monthly/custom) · smart auto-assignment (count/time/difficulty/weighted fairness) · preference-aware (prefer/neutral/avoid per template) · calendar availability penalty · photo proof · complete/snooze/swap/emergency reassign
- **Task marketplace:** list a task for others to claim with bonus points
- **Gamification:** points · streaks · 26 badges · per-household leaderboard
- **Proposals & voting:** members propose new tasks; group votes before activation
- **Real-time:** Django Channels WebSocket — live chat, instant notifications, emergency reassign broadcast
- **Calendar sync:** Google Calendar (OAuth, webhook push, incremental delta sync, writeback of task events) · Outlook / Microsoft Graph (delta-link sync, OAuth token refresh)
- **Notifications:** in-app with action deep-links · per-user preferences · quiet hours
- **Dark mode:** persisted to localStorage via Quasar Dark plugin
