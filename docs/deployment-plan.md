# ChoreSync Local Deployment Plan

## Purpose

This document defines a practical deployment plan for running the full ChoreSync system natively on a laptop, without containers, while keeping the application usable during temporary internet outages.

The plan is based on the actual codebase:

- Django backend with Channels and Celery
- Vue/Vite web frontend
- PostgreSQL
- Redis
- Celery worker and Celery beat
- static frontend build served through a reverse proxy
- optional external access when internet is available

Note: the repository web frontend is Vue, not React. The portability guidance in this document is written so the SPA can later be deployed elsewhere with minimal change.

---

## 1. Recommended Architecture

### 1.1 Target local architecture

Run the laptop as a small single-host application server with these components:

- `PostgreSQL`
  - persistent relational store for users, groups, tasks, calendars, notifications, and sync state
- `Redis`
  - Celery broker/result backend
  - Channels backend for WebSocket fan-out
- `Daphne`
  - ASGI server for Django HTTP + WebSocket traffic
- `Celery worker`
  - background task execution
- `Celery beat`
  - scheduled jobs such as reminders, recurring task generation, calendar maintenance, and cleanup
- `Caddy` or `Nginx`
  - reverse proxy
  - serves built frontend
  - terminates HTTPS when needed
  - proxies API, WebSocket, and media requests to backend

### 1.2 Recommended network layout

- External-facing process:
  - reverse proxy only
- Internal-only processes:
  - PostgreSQL on `127.0.0.1:5432`
  - Redis on `127.0.0.1:6379`
  - Daphne on `127.0.0.1:8000`
  - Celery worker and beat with no public network exposure

### 1.3 Request flow

- Browser requests:
  - `/` -> frontend static build
  - `/api/*` -> Django via Daphne
  - `/admin/*` -> Django via Daphne
  - `/ws/*` -> Django Channels via Daphne
  - `/media/*` -> media directory
- SPA routing:
  - unknown non-API routes fall back to `index.html`

### 1.4 Why this architecture fits the codebase

- Django already provides static/media settings in [`backend/chore_sync/settings.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/settings.py).
- Celery and Redis are already configured there.
- Channels already supports Redis-backed operation if `CELERY_BROKER_URL` is set.
- The frontend already builds cleanly with Vite in [`frontend/vite.config.ts`](/home/mahamad/Projects/ChoreSync/frontend/vite.config.ts).

---

## 2. Production-Like Local Topology

### 2.1 Ports

- Reverse proxy:
  - `80`
  - `443`
- Daphne:
  - `127.0.0.1:8000`
- PostgreSQL:
  - `127.0.0.1:5432`
- Redis:
  - `127.0.0.1:6379`

### 2.2 Filesystem locations

Recommended persistent directories:

- application source:
  - `/opt/choresync` or equivalent user-owned location
- virtual environment:
  - `/opt/choresync/.venv`
- frontend build:
  - `/opt/choresync/frontend/dist`
- backend media:
  - `/opt/choresync/backend/media`
- backend secrets:
  - `/opt/choresync/backend/secrets.env`
- logs:
  - `/var/log/choresync/` or user-owned local log directory
- backups:
  - `/opt/choresync/backups/`

On Windows, the same layout can be mirrored under a stable directory such as:

- `C:\ChoreSync\...`

---

## 3. Deployment Workflow

### 3.1 Prepare the laptop

Install natively:

- Python 3.11+
- Node.js
- PostgreSQL
- Redis
- Caddy or Nginx

Optional for external access:

- Cloudflare Tunnel client or another tunnel/domain solution

### 3.2 Prepare the backend

Create and install the virtual environment:

```bash
cd /path/to/ChoreSync
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run database setup:

```bash
createdb choresync
python backend/manage.py migrate
python backend/seed_badges.py
```

### 3.3 Prepare the frontend

Install and build:

```bash
cd frontend
npm install
npm run build
```

The deployable web artifact is the static build in:

- [`frontend/dist`](/home/mahamad/Projects/ChoreSync/frontend/dist)

### 3.4 Configure environment

The backend already reads:

- `DATABASE_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `FRONTEND_APP_URL`
- `BACKEND_BASE_URL`
- OAuth and webhook values
- `FIELD_ENCRYPTION_KEY`

via [`backend/chore_sync/settings.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/settings.py).

Use `backend/secrets.env` as the main deployment env file.

### 3.5 Start core services

Order:

1. PostgreSQL
2. Redis
3. Daphne
4. Celery worker
5. Celery beat
6. Reverse proxy

---

## 4. Environment Configuration

### 4.1 Recommended backend environment example

```env
DEBUG=False
SECRET_KEY=replace-me
FIELD_ENCRYPTION_KEY=replace-me

DATABASE_URL=postgres://choresync_user:strongpassword@127.0.0.1:5432/choresync

CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

ALLOWED_HOSTS=localhost,127.0.0.1,choresync.local,mydomain.example
FRONTEND_APP_URL=https://choresync.local
BACKEND_BASE_URL=https://choresync.local

CSRF_TRUSTED_ORIGINS=https://choresync.local,https://mydomain.example
CORS_ALLOWED_ORIGINS=https://choresync.local,https://mydomain.example
CORS_ALLOW_ALL_ORIGINS=False

GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=https://choresync.local/api/calendar/google/callback/
GOOGLE_WEBHOOK_CALLBACK_URL=https://mydomain.example/api/calendar/google/webhook/

MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
MICROSOFT_TENANT_ID=common
OUTLOOK_OAUTH_REDIRECT_URI=https://choresync.local/api/calendar/outlook/callback/
OUTLOOK_WEBHOOK_SECRET=replace-me

OLLAMA_URL=http://127.0.0.1:11434/api/chat
OLLAMA_MODEL=phi3:mini

EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=True
```

### 4.2 Local-only variant

For strictly local-only use, keep:

- `ALLOWED_HOSTS=localhost,127.0.0.1`
- `FRONTEND_APP_URL=http://localhost`
- `BACKEND_BASE_URL=http://localhost`
- webhook callback values empty unless you enable external access

### 4.3 Frontend environment

Current frontend environment files include hardcoded API origins such as:

- [`frontend/.env`](/home/mahamad/Projects/ChoreSync/frontend/.env)
- [`frontend/.env.local`](/home/mahamad/Projects/ChoreSync/frontend/.env.local)

Current issue:

- `VITE_API_BASE_URL` is host-specific and can tie a build to one machine or one network.

Recommendation:

- use runtime-configurable API base URLs or same-origin URLs
- avoid hardcoding backend origin into the shipped build

---

## 5. Frontend Portability Plan

### 5.1 Current frontend coupling

The frontend currently derives API and socket origins from build-time environment variables in:

- [`frontend/src/services/api.ts`](/home/mahamad/Projects/ChoreSync/frontend/src/services/api.ts)
- [`frontend/src/services/NotificationSocketService.ts`](/home/mahamad/Projects/ChoreSync/frontend/src/services/NotificationSocketService.ts)
- [`frontend/src/services/eventService.ts`](/home/mahamad/Projects/ChoreSync/frontend/src/services/eventService.ts)

This makes the build less portable across:

- localhost
- LAN usage
- domain-based usage
- future hosted deployment

### 5.2 Recommended frontend portability model

Use one of these two approaches:

- Preferred:
  - serve frontend and backend under the same origin
  - use relative URLs for HTTP, WebSocket, and SSE
- Alternative:
  - inject runtime config at startup using `/app-config.js`

### 5.3 Recommended code changes

#### `frontend/src/services/api.ts`

Current concept:

```ts
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
```

Recommended:

```ts
declare global {
  interface Window {
    __APP_CONFIG__?: {
      apiBaseUrl?: string;
      wsBaseUrl?: string;
    };
  }
}

const baseURL = window.__APP_CONFIG__?.apiBaseUrl ?? '';
```

With same-origin deployment this becomes:

- API requests go to `/api/...`
- no hardcoded host required

#### `frontend/src/services/NotificationSocketService.ts`

Recommended:

```ts
const defaultWsBase = window.location.origin.replace(/^http/, 'ws');
const WS_BASE = window.__APP_CONFIG__?.wsBaseUrl ?? defaultWsBase;
```

#### `frontend/src/services/eventService.ts`

Recommended SSE:

```ts
const url = `${window.__APP_CONFIG__?.apiBaseUrl ?? ''}/api/events/stream/`;
```

or just:

```ts
const url = `/api/events/stream/`;
```

### 5.4 Runtime config file

Create a static runtime config file served beside `index.html`:

```js
window.__APP_CONFIG__ = {
  apiBaseUrl: "",
  wsBaseUrl: ""
};
```

That allows:

- local same-origin mode
- domain mode
- tunnel mode
- later hosted deployment with minimal or no rebuild

### 5.5 Outcome

This change makes the frontend portable because:

- the build stops depending on one backend hostname
- environment-specific values move to runtime config or reverse proxy routing
- future non-laptop deployment only needs proxy/config changes

---

## 6. Reverse Proxy Configuration

### 6.1 Why a reverse proxy is required

It provides:

- a single origin for SPA + API
- clean static serving for the built frontend
- WebSocket proxy support
- optional HTTPS
- safe external exposure when internet is available

### 6.2 Caddy example

```caddyfile
choresync.local {
    root * /opt/choresync/frontend/dist
    encode gzip zstd
    file_server

    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle /admin/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle /ws/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle /media/* {
        root * /opt/choresync/backend
        file_server
    }

    try_files {path} /index.html
}
```

### 6.3 Nginx example

```nginx
server {
    listen 80;
    server_name choresync.local;

    root /opt/choresync/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location /media/ {
        alias /opt/choresync/backend/media/;
    }

    location / {
        try_files $uri /index.html;
    }
}
```

---

## 7. Offline and Reconnection Strategy

### 7.1 What works offline because it is local

These flows should continue working while the laptop has no internet access:

- user login and session/JWT validation
- group management
- task templates and task occurrences
- assignment logic
- task completion
- task snoozing
- swaps and marketplace
- notifications over local WebSocket
- chat over local WebSocket
- stats, badges, and leaderboard
- photo proof uploads
- local AI assistant if Ollama runs locally

These all depend mainly on:

- PostgreSQL
- Redis
- Daphne
- Celery

and not on external network connectivity.

### 7.2 What pauses when offline

- Google OAuth
- Outlook OAuth
- Google/Outlook sync and webhooks
- remote email sending
- any hosted AI provider if you stop using local Ollama

### 7.3 Recovery after connectivity returns

The codebase already includes periodic recovery jobs in [`backend/chore_sync/tasks.py`](/home/mahamad/Projects/ChoreSync/backend/chore_sync/tasks.py):

- Google:
  - watch renewal
  - catch-up sync
- Outlook:
  - token refresh
  - subscription renewal
  - catch-up sync

Recommended operating model:

- keep Celery beat and worker running at all times
- allow temporary external failures
- let recovery jobs restore sync state automatically after connectivity returns

### 7.4 Additional recommended hardening

- enable Redis persistence so queued tasks survive restart
- keep sync errors visible in logs
- if possible, add admin-visible “last sync failed” status later

---

## 8. Background Tasks and Queue Behaviour

### 8.1 Required always-on processes

- `celery -A chore_sync worker`
- `celery -A chore_sync beat`

### 8.2 Why both are needed locally

- Worker:
  - executes async tasks and sync jobs
- Beat:
  - drives periodic reminders, recurring tasks, calendar maintenance, cleanup, and suggestions

### 8.3 Recommended worker commands

Worker:

```bash
cd /opt/choresync/backend
/opt/choresync/.venv/bin/celery -A chore_sync worker --loglevel=INFO
```

Beat:

```bash
cd /opt/choresync/backend
/opt/choresync/.venv/bin/celery -A chore_sync beat --loglevel=INFO
```

### 8.4 Queue durability

For Redis:

- enable AOF
- keep snapshotting enabled
- store Redis persistence files on local disk, not temp storage

---

## 9. Startup Strategy

### 9.1 Goal

The laptop should boot and restore the full stack automatically without manual shell sessions.

### 9.2 Linux recommendation: `systemd`

Create services for:

- `choresync-daphne.service`
- `choresync-celery-worker.service`
- `choresync-celery-beat.service`
- `caddy.service` or `nginx.service`

PostgreSQL and Redis should use their standard OS services.

### 9.3 Example `systemd` service: Daphne

```ini
[Unit]
Description=ChoreSync Daphne
After=network.target postgresql.service redis.service

[Service]
User=choresync
Group=choresync
WorkingDirectory=/opt/choresync/backend
Environment=DJANGO_SETTINGS_MODULE=chore_sync.settings
ExecStart=/opt/choresync/.venv/bin/daphne -b 127.0.0.1 -p 8000 chore_sync.asgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 9.4 Example `systemd` service: Celery worker

```ini
[Unit]
Description=ChoreSync Celery Worker
After=network.target postgresql.service redis.service

[Service]
User=choresync
Group=choresync
WorkingDirectory=/opt/choresync/backend
Environment=DJANGO_SETTINGS_MODULE=chore_sync.settings
ExecStart=/opt/choresync/.venv/bin/celery -A chore_sync worker --loglevel=INFO
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 9.5 Example `systemd` service: Celery beat

```ini
[Unit]
Description=ChoreSync Celery Beat
After=network.target postgresql.service redis.service

[Service]
User=choresync
Group=choresync
WorkingDirectory=/opt/choresync/backend
Environment=DJANGO_SETTINGS_MODULE=chore_sync.settings
ExecStart=/opt/choresync/.venv/bin/celery -A chore_sync beat --loglevel=INFO
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 9.6 macOS and Windows

- macOS:
  - use `launchd`
- Windows:
  - use Task Scheduler or a service wrapper such as NSSM/WinSW

The same process split should still apply.

---

## 10. Persistent Data Protection

### 10.1 Data that must persist

- PostgreSQL data directory
- Redis AOF/RDB files
- [`backend/media`](/home/mahamad/Projects/ChoreSync/backend/media)
- [`backend/secrets.env`](/home/mahamad/Projects/ChoreSync/backend/secrets.env)
- `FIELD_ENCRYPTION_KEY`

### 10.2 Backup recommendation

Nightly PostgreSQL backup:

```bash
pg_dump -Fc choresync > /opt/choresync/backups/choresync-$(date +%F).dump
```

Daily media backup:

```bash
rsync -a /opt/choresync/backend/media/ /opt/choresync/backups/media/
```

Also back up:

- `backend/secrets.env`
- the encryption key

Without the encryption key, encrypted external credentials in the database cannot be recovered.

---

## 11. External Access Strategy

### 11.1 Local-first default

The system should always work locally without any external dependency.

Default local mode:

- no public exposure
- no tunnel required
- app accessed via:
  - `http://localhost`
  - `https://choresync.local`
  - LAN hostname if needed

### 11.2 Optional external mode when internet is available

Preferred approach:

- expose only the reverse proxy through a secure tunnel

Why:

- PostgreSQL and Redis stay private
- Daphne stays private
- only one controlled ingress path is public

The repository already includes tunnel helper scripts in [`scripts/`](/home/mahamad/Projects/ChoreSync/scripts).

### 11.3 Domain/tunnel configuration requirements

When externally reachable, update:

- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `CORS_ALLOWED_ORIGINS`
- `FRONTEND_APP_URL`
- `BACKEND_BASE_URL`
- OAuth redirect URIs
- webhook callback URLs

### 11.4 Security rule

Never expose:

- PostgreSQL directly
- Redis directly
- Daphne directly

Only expose:

- the reverse proxy entrypoint

---

## 12. Security Considerations for Laptop Hosting

### 12.1 Process isolation

- run the app under a dedicated OS user if possible
- do not run as an administrator/root user unnecessarily

### 12.2 Network hardening

- bind PostgreSQL and Redis to loopback only
- keep Daphne loopback-only behind the reverse proxy
- expose only the reverse proxy

### 12.3 Secrets handling

- keep `backend/secrets.env` out of version control
- restrict permissions to owner-only
- protect OAuth client secrets and SMTP credentials

### 12.4 HTTPS

- use HTTPS for any external access
- if using a tunnel or domain, terminate TLS at the reverse proxy

### 12.5 OAuth and webhook considerations

- only configure publicly reachable webhook URLs when external access is available
- keep redirect URIs consistent with actual reachable entrypoints

### 12.6 Physical and laptop-specific risks

- sleep mode can pause services
- battery drain or sudden shutdown is equivalent to server downtime
- Wi-Fi changes can invalidate LAN access assumptions

---

## 13. Startup Checklist

At deploy time:

1. Install native dependencies
2. Configure PostgreSQL
3. Configure Redis persistence
4. Create backend virtual environment
5. Install Python dependencies
6. Install frontend dependencies
7. Build frontend
8. Configure `backend/secrets.env`
9. Run migrations
10. Seed badges
11. Configure reverse proxy
12. Configure startup services
13. Validate local access
14. Validate WebSocket connectivity
15. Validate Celery worker and beat execution
16. Validate media upload path

---

## 14. Risks and Limitations of Hosting from a Laptop

### 14.1 Operational limits

- the laptop is a single point of failure
- closing the lid, rebooting, sleeping, or losing power stops the whole system

### 14.2 Reliability limits

- background syncs and webhook handling depend on the laptop being online and reachable
- external access is inherently less stable than server hosting

### 14.3 Performance limits

- PostgreSQL, Redis, Celery, and the reverse proxy all consume resources continuously
- heavy sync periods or local AI inference can impact normal laptop responsiveness

### 14.4 Security limits

- a personal laptop is usually less hardened than a dedicated server
- accidental exposure risk is higher if ports are opened directly instead of tunneled

---

## 15. Recommended Final Operating Model

### Baseline local mode

- Reverse proxy serves the built SPA and proxies Django
- PostgreSQL and Redis run locally
- Daphne runs on loopback
- Celery worker and beat run continuously
- users access the app on the laptop itself or over the local network

### Optional external mode

- same architecture
- add domain or secure tunnel to the reverse proxy only
- update env values for hosts, CSRF, CORS, OAuth, and webhook callbacks

### Portability target

The web frontend should be changed so that:

- it uses same-origin or runtime config
- it has no hardcoded backend origin
- it can be moved later to another laptop, VM, or hosted machine with only:
  - env changes
  - reverse proxy changes
  - optional runtime config changes

---

## 16. Recommended Next Changes in This Repository

### High-value deployment changes

- Replace hardcoded frontend API origin usage with runtime config or same-origin defaults.
- Standardise WebSocket and SSE URL derivation the same way.
- Add explicit reverse-proxy deployment instructions to the repository.
- Add native service definitions for boot startup.
- Add backup scripts for PostgreSQL and media.

### High-value local reliability changes

- Keep Redis-backed Channels enabled in local deployment by setting `CELERY_BROKER_URL`.
- Add clearer logging around reconnecting calendar sync jobs.
- Add an internal health page or admin status indicators later for:
  - Redis
  - Celery worker
  - Celery beat
  - last successful provider sync

---

## Conclusion

The most practical production-like local deployment for ChoreSync is:

- static frontend build served by a reverse proxy
- Django served by Daphne behind that proxy
- PostgreSQL and Redis running locally
- Celery worker and beat always on
- same-origin frontend-to-backend communication
- optional external access only through a controlled proxy/tunnel

This gives the system the best chance of:

- working fully on the laptop without internet
- recovering automatically when connectivity returns
- remaining portable for later deployment elsewhere with minimal frontend change
