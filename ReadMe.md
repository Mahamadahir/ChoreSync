# ChoreSync

ChoreSync is a Django + DRF backend with a Vue/Quasar frontend for coordinating household/group chores. It supports email/password auth, email verification, password reset, Google/Microsoft sign-in, and an in-app calendar view of events/tasks.

## Repo Structure
- `backend/` Django project (session auth, DRF endpoints, Postgres config, models/services)
- `frontend/` Vue 3 + Quasar SPA (Vite dev server)
- `ProgressTracker.html` / `progress-data.js` track planned features/tests

## Backend (Django)
1. Create/activate venv (PowerShell example):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   (macOS/Linux: `source .venv/bin/activate`)
2. Install deps:
   ```powershell
   pip install -r requirements.txt
   ```
3. Set env in `backend/secrets.env` (loaded by settings):
   ```env
   SECRET_KEY=...
   DEBUG=True
   ALLOWED_HOSTS=127.0.0.1,localhost
   DATABASE_URL=postgres://choresync_user:choreSync@localhost:5432/choresync
   EMAIL_HOST_USER=you@example.com
   EMAIL_HOST_PASSWORD=...
   EMAIL_USE_TLS=True
   FRONTEND_VERIFY_EMAIL_URL=http://localhost:5173/verify-email
   GOOGLE_OAUTH_CLIENT_ID=<your-google-client-id>
   GOOGLE_OAUTH_CLIENT_SECRET=<your-google-client-secret>
   GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/calendar/google/callback/
   MICROSOFT_CLIENT_ID=<your-azure-app-client-id>
   MICROSOFT_TENANT_ID=common
   ```
4. Apply migrations:
   ```powershell
   cd backend
   python manage.py migrate
   ```
5. Run server (defaults to 8000):
   ```powershell
   python manage.py runserver
   ```

## Frontend (Vue/Quasar)
1. Install Node.js 20+.
2. Install deps:
   ```powershell
   cd frontend
   npm install
   ```
3. Env in `frontend/.env`:
   ```env
   VITE_API_BASE_URL=http://localhost:8000
   VITE_GOOGLE_CLIENT_ID=<your-google-client-id>
   VITE_MSAL_CLIENT_ID=<your-azure-app-client-id>
   VITE_MSAL_AUTHORITY=https://login.microsoftonline.com/common
   ```
4. Dev server (defaults to 5173):
   ```powershell
   npm run dev
   ```

## Calendar View & FullCalendar CSS
- We use FullCalendar v5 (packages include CSS).
- Imports in `CalendarView.vue` reference `@fullcalendar/common/daygrid/timegrid` CSS from `node_modules`.
- If you need to vendor CSS locally (offline/airgapped), run from `frontend/`:
  ```powershell
  Copy-Item node_modules/@fullcalendar/common/main.min.css src/assets/fullcalendar.css
  Copy-Item node_modules/@fullcalendar/daygrid/main.min.css src/assets/fullcalendar-daygrid.css
  Copy-Item node_modules/@fullcalendar/timegrid/main.min.css src/assets/fullcalendar-timegrid.css
  ```
  Then update `CalendarView.vue` imports to point to `../assets/*.css`. Keep these files in sync if you upgrade FullCalendar.

## Features Snapshot
- Auth: signup/login/logout, email verification, password reset, profile update, timezone stored on user.
- Social auth: Google & Microsoft login/signup (ID token verification on backend).
- Calendar: read events and create manual events (UTC stored; rendered in local time), Monday-start week.

## Running Tests (backend)
```powershell
cd backend
python manage.py check
python -m pytest
```

## Notes
- Session auth is used; CORS/CSRF are relaxed for local dev. Tighten for production.
- External calendar todo sync is intentionally out of scope (events only).
