# Bugs found

## 1. Microsoft SSO broken ✅ FIXED

**Symptom:** "Microsoft client ID missing. Check your .env."

**Root cause:** `frontend/.env.local` only contained `VITE_API_BASE_URL`. `VITE_MSAL_CLIENT_ID` and `VITE_MSAL_AUTHORITY` were never added. Google SSO had the same issue (`VITE_GOOGLE_CLIENT_ID` also missing).

**Fix:** Added all three missing vars to `frontend/.env.local` (values copied from `backend/secrets.env`):
```
VITE_GOOGLE_CLIENT_ID=...
VITE_MSAL_CLIENT_ID=...
VITE_MSAL_AUTHORITY=https://login.microsoftonline.com/common
```
Restart the Vite dev server after changing `.env.local`.

---

## 2. Dark mode — calendar doesn't go dark ✅ FIXED

**Symptom:** Toggling dark mode leaves the FullCalendar grid white/light.

**Root cause:** FullCalendar v5 ships its own CSS with hardcoded colours. Quasar's dark plugin only adds `body.body--dark` — FullCalendar has no knowledge of it.

**Fix:** Added a non-scoped `<style>` block to `CalendarView.vue` with explicit CSS overrides targeting `body.body--dark .fc` and all major FullCalendar sub-elements.

---

## 3. Admin portal missing styles / static files 404 ✅ FIXED

**Symptom:** `/static/admin/css/...`, `/static/admin/js/...` all return 404 under Daphne.

**Root cause:** Django's `runserver` has built-in static file serving for DEBUG mode. Daphne (ASGI) does not. No `STATIC_ROOT` was configured and WhiteNoise was not installed.

**Fix:**
1. Added `whitenoise>=6.7.0` to `requirements.txt`
2. Added `whitenoise.middleware.WhiteNoiseMiddleware` to `MIDDLEWARE` (right after `SecurityMiddleware`)
3. Added `STATIC_ROOT = BASE_DIR / 'staticfiles'` and `STATICFILES_STORAGE` to settings
4. Run once after pulling: `python manage.py collectstatic --noinput`

---

## 4. Microsoft SSO slow (5–30 s on first login after server start) ✅ FIXED

**Symptom:** Microsoft login popup completes quickly but the backend takes a long time to create the user / return the session.

**Root cause:** `sign_in_with_microsoft` created a new `PyJWKClient` on every request. `PyJWKClient.__init__` makes a live HTTPS request to `https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys` to download the public key set. DNS + TLS + HTTP round-trip to Microsoft on every login.

**Fix:** Cached the `PyJWKClient` instance in a module-level dict `_ms_jwks_clients`. Keys are fetched once on first login, then served from memory. Subsequent logins are near-instant. (Password reset email delay is an unrelated SMTP latency — not a code bug.)

---

## 5. Calendar dark mode — toolbar ribbon stays light ✅ FIXED

**Symptom:** Grid cells go dark but the top toolbar (prev/next, today, month/week/day buttons) stays light-grey.

**Root cause (A):** `.fc-toolbar` background was never targeted in the dark mode CSS.

**Root cause (B):** FullCalendar's own CSS uses `.fc .fc-button-primary` (2-class specificity = 0,2,0). The overrides used only `.fc-button-primary` (1-class = 0,1,0) and lost the cascade.

**Fix:** Added explicit `body.body--dark .fc .fc-toolbar { background: #272727; }` and updated all button overrides to use `body.body--dark .fc .fc-button-primary` to match FullCalendar's specificity.
# personal fixes
## Reduce number of buttons
## dont use the same name of test - when demonstating to someone - use different names for test tasks, groups etc

# code fixes

## follow tutiorial for ai implementation
## stich by google 
## clean up UI as well


## MAke use of previous data - task of this type has been prefered by harris 90% of the time -> so therefore 
## Move require phone + voting & fairness algorithm into new task 