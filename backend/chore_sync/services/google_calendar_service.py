from __future__ import annotations

import datetime
import logging
import secrets
import uuid
from typing import Optional, List

from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from django.utils import timezone

from chore_sync.models import ExternalCredential, Calendar, Event

logger = logging.getLogger(__name__)


GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]


class GoogleEventConflict(Exception):
    """Raised when Google reports a conflicting update (etag mismatch)."""


class GoogleCalendarService:
    def __init__(self, user):
        self.user = user
        self.client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "")
        self.client_secret = getattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "")
        self.redirect_uri = getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "")
        if not self.client_id or not self.client_secret:
            raise ValueError("Google OAuth is not configured.")

    def _flow(self) -> Flow:
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uris": [self.redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=GOOGLE_SCOPES,
        )

    def build_auth_url(self) -> str:
        flow = self._flow()
        flow.redirect_uri = self.redirect_uri
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes=False,
            prompt="consent",
        )
        return auth_url

    def exchange_code(self, code: str) -> ExternalCredential:
        flow = self._flow()
        flow.redirect_uri = self.redirect_uri
        try:
            flow.fetch_token(code=code)
        except Exception as exc:
            logger.exception("Failed to fetch Google token", exc_info=exc)
            raise
        creds = flow.credentials
        account_email = None
        decoded_info = {}
        if creds.id_token:
            try:
                decoded_info = google_id_token.verify_oauth2_token(
                    creds.id_token, Request(), self.client_id
                )
                account_email = decoded_info.get("email")
            except Exception as exc:  # pragma: no cover - log and continue
                logger.warning("Failed to decode id_token for email: %s", exc)
        secret_payload = self._creds_to_dict(creds)
        cred, _ = ExternalCredential.objects.update_or_create(
            user=self.user,
            provider="google",
            account_email=account_email,
            defaults={"secret": secret_payload},
        )
        Calendar.objects.update_or_create(
            user=self.user,
            provider="google",
            external_id="primary",
            defaults={
                "name": "Google Calendar (Primary)",
                "sync_enabled": True,
                "include_in_availability": True,
                "timezone": decoded_info.get("timezone", "UTC"),
            },
        )
        return cred

    def _load_credentials(self) -> Optional[Credentials]:
        cred = (
            ExternalCredential.objects.filter(user=self.user, provider="google")
            .order_by("-last_refreshed_at")
            .first()
        )
        if not cred:
            return None
        data = cred.secret or {}
        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri"),
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=data.get("scopes", GOOGLE_SCOPES),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            cred.secret = self._creds_to_dict(creds)
            cred.save(update_fields=["secret", "last_refreshed_at"])
        return creds

    def list_calendars(self, min_access_role: str = "reader") -> List[dict]:
        """
        List Google calendars for the authenticated user.
        Returns minimal metadata plus a derived writable flag.
        """
        creds = self._load_credentials()
        if not creds:
            raise ValueError("Google credentials not found. Connect first.")
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        calendars: List[dict] = []
        page_token = None
        while True:
            result = (
                service.calendarList()
                .list(minAccessRole=min_access_role, pageToken=page_token)
                .execute()
            )
            for item in result.get("items", []):
                access_role = item.get("accessRole")
                calendars.append(
                    {
                        "id": item.get("id"),
                        "summary": item.get("summary"),
                        "accessRole": access_role,
                        "primary": item.get("primary", False),
                        "color": item.get("backgroundColor") or item.get("foregroundColor") or item.get("colorId"),
                        "writable": access_role in ("owner", "writer"),
                        "timeZone": item.get("timeZone"),
                    }
                )
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return calendars

    def sync_events(self, calendar: Optional[Calendar] = None, force_full: bool = False) -> int:
        creds = self._load_credentials()
        if not creds:
            raise ValueError("Google credentials not found. Connect first.")
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        calendars = (
            [calendar]
            if calendar
            else Calendar.objects.filter(user=self.user, provider="google", sync_enabled=True)
        )
        total = 0
        for cal in calendars:
            total += self._sync_single_calendar(service, cal, force_full=force_full)
        return total

    def _sync_single_calendar(self, service, cal: Calendar, force_full: bool = False) -> int:
        calendar_id = cal.external_id or "primary"
        count = 0
        page_token = None
        use_sync_token = bool(cal.sync_token) and not force_full
        time_min = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc).isoformat()

        while True:
            try:
                params = {
                    "calendarId": calendar_id,
                    "singleEvents": True,
                    "orderBy": "startTime",
                    "maxResults": 500,
                }
                if use_sync_token:
                    params["syncToken"] = cal.sync_token
                else:
                    params["timeMin"] = time_min
                    if page_token:
                        params["pageToken"] = page_token
                events_result = service.events().list(**params).execute()
            except HttpError as exc:
                if exc.resp is not None and exc.resp.status == 410 and use_sync_token:
                    # Sync token expired, fall back to full sync
                    use_sync_token = False
                    cal.sync_token = None
                    cal.save(update_fields=["sync_token"])
                    continue
                logger.exception("Failed syncing Google calendar %s", calendar_id, exc_info=exc)
                break
            items = events_result.get("items", [])
            for item in items:
                start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
                end = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
                if not start or not end:
                    continue
                is_all_day = "T" not in start
                start_dt = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
                end_dt = datetime.datetime.fromisoformat(end.replace("Z", "+00:00"))
                updated_str = item.get("updated")
                updated_dt = None
                if updated_str:
                    try:
                        updated_dt = datetime.datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                    except Exception:
                        updated_dt = None
                existing = Event.objects.filter(external_event_id=item.get("id"), calendar=cal).order_by("id")
                ev = existing.first()
                if ev:
                    existing.exclude(pk=ev.pk).delete()
                    for field, val in {
                        "title": item.get("summary", "(no title)"),
                        "description": item.get("description", "") or "",
                        "start": start_dt,
                        "end": end_dt,
                        "is_all_day": is_all_day,
                        "blocks_availability": cal.include_in_availability,
                        "source": "external",
                        "status": item.get("status", "confirmed"),
                        "external_calendar_id": calendar_id,
                        "external_etag": item.get("etag"),
                        "external_updated": updated_dt,
                    }.items():
                        setattr(ev, field, val)
                    ev.save()
                else:
                    Event.objects.create(
                        external_event_id=item.get("id"),
                        calendar=cal,
                        title=item.get("summary", "(no title)"),
                        description=item.get("description", "") or "",
                        start=start_dt,
                        end=end_dt,
                        is_all_day=is_all_day,
                        blocks_availability=cal.include_in_availability,
                        source="external",
                        status=item.get("status", "confirmed"),
                        external_calendar_id=calendar_id,
                        external_etag=item.get("etag"),
                        external_updated=updated_dt,
                    )
                count += 1
            page_token = events_result.get("nextPageToken")
            if use_sync_token or not page_token:
                next_sync = events_result.get("nextSyncToken")
                if next_sync:
                    cal.sync_token = next_sync
                    cal.save(update_fields=["sync_token"])
                break
        cal.last_synced_at = timezone.now()
        cal.save(update_fields=["last_synced_at"])
        self._ensure_watch(service, cal)
        return count

    def _build_event_body(self, ev: Event) -> dict:
        body = {
            "summary": ev.title,
            "description": ev.description or "",
        }
        if ev.is_all_day:
            body["start"] = {"date": ev.start.date().isoformat()}
            body["end"] = {"date": ev.end.date().isoformat()}
        else:
            body["start"] = {
                "dateTime": ev.start.astimezone(datetime.timezone.utc).isoformat(),
                "timeZone": "UTC",
            }
            body["end"] = {
                "dateTime": ev.end.astimezone(datetime.timezone.utc).isoformat(),
                "timeZone": "UTC",
            }
        return body

    def _ensure_watch(self, service, cal: Calendar) -> None:
        callback = getattr(settings, "GOOGLE_WEBHOOK_CALLBACK_URL", "")
        if not callback:
            return  # no callback configured; skip watch
        renew_margin = datetime.timedelta(minutes=30)
        now = datetime.datetime.now(datetime.timezone.utc)
        if cal.watch_expires_at and cal.watch_expires_at - now > renew_margin:
            return
        # stop any existing channel before starting a new one
        self._stop_watch(service, cal)
        channel_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(16)
        try:
            result = (
                service.events()
                .watch(
                    calendarId=cal.external_id or "primary",
                    body={
                        "id": channel_id,
                        "type": "web_hook",
                        "address": callback,
                        "token": token,
                    },
                )
                .execute()
            )
        except HttpError as exc:
            logger.exception("Failed to start watch channel for calendar %s", cal.id, exc_info=exc)
            return
        except Exception as exc:
            logger.exception("Unexpected error starting watch channel for calendar %s", cal.id, exc_info=exc)
            return
        resource_id = result.get("resourceId")
        expiration_ms = result.get("expiration")
        expires_at = None
        if expiration_ms:
            try:
                expires_at = datetime.datetime.fromtimestamp(int(expiration_ms) / 1000.0, tz=datetime.timezone.utc)
            except Exception:
                expires_at = None
        cal.channel_id = channel_id
        cal.resource_id = resource_id
        cal.webhook_token = token
        cal.watch_expires_at = expires_at
        cal.save(update_fields=["channel_id", "resource_id", "webhook_token", "watch_expires_at"])

    def _stop_watch(self, service, cal: Calendar) -> None:
        if not cal.channel_id or not cal.resource_id:
            return
        try:
            service.channels().stop(body={"id": cal.channel_id, "resourceId": cal.resource_id}).execute()
        except Exception:
            logger.debug("Failed to stop watch channel for calendar %s", cal.id, exc_info=True)
        cal.channel_id = None
        cal.resource_id = None
        cal.watch_expires_at = None
        cal.webhook_token = None
        cal.save(update_fields=["channel_id", "resource_id", "watch_expires_at", "webhook_token"])

    def ensure_watch_channel(self, cal: Calendar) -> None:
        creds = self._load_credentials()
        if not creds:
            raise ValueError("Google credentials not found. Connect first.")
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._ensure_watch(service, cal)

    def stop_watch_channel(self, cal: Calendar) -> None:
        creds = self._load_credentials()
        if not creds:
            raise ValueError("Google credentials not found. Connect first.")
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._stop_watch(service, cal)

    def _should_push(self, event: Event) -> bool:
        return (
            event.calendar.provider == "google"
            and getattr(event.calendar, "writable", True)
        )

    def push_created_event(self, event: Event) -> str:
        """
        Push a single locally-created event to Google. Only applies to google calendars.
        Returns the external_event_id that was stored.
        """
        if not self._should_push(event):
            return ""
        creds = self._load_credentials()
        if not creds:
            logger.warning("Google credentials not found for user %s; skipping push.", self.user)
            return ""
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        cal_id = event.calendar.external_id or "primary"
        body = self._build_event_body(event)
        try:
            result = service.events().insert(calendarId=cal_id, body=body).execute()
        except HttpError as exc:
            if exc.resp is not None and exc.resp.status in (409, 412):
                raise GoogleEventConflict("Google event was changed remotely.")
            logger.exception("Failed to push created event %s to Google", event.id, exc_info=exc)
            return ""
        except Exception as exc:
            logger.exception("Failed to push created event %s to Google", event.id, exc_info=exc)
            return ""
        external_id = result.get("id") if isinstance(result, dict) else None
        event.external_event_id = external_id
        event.external_calendar_id = cal_id
        event.external_etag = result.get("etag")
        updated_str = result.get("updated")
        if updated_str:
            try:
                event.external_updated = datetime.datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            except Exception:
                event.external_updated = None
        event.save(update_fields=["external_event_id", "external_calendar_id", "external_etag", "external_updated"])
        return external_id or ""

    def push_updated_event(self, event: Event) -> str:
        """
        Push a single locally-updated event to Google. If no external_event_id exists, creates it first.
        Returns the external_event_id.
        """
        if not self._should_push(event):
            return ""
        creds = self._load_credentials()
        if not creds:
            logger.warning("Google credentials not found for user %s; skipping push.", self.user)
            return ""
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        cal_id = event.calendar.external_id or "primary"
        body = self._build_event_body(event)
        if event.external_event_id:
            try:
                remote = service.events().get(calendarId=cal_id, eventId=event.external_event_id).execute()
                remote_etag = remote.get("etag")
                if event.external_etag and remote_etag and remote_etag != event.external_etag:
                    raise GoogleEventConflict("Google event was changed remotely.")
            except GoogleEventConflict:
                raise
            except HttpError as exc:
                logger.warning("Failed to fetch remote Google event %s for conflict check", event.id, exc_info=exc)
            except Exception as exc:
                logger.exception("Unexpected error checking Google event %s", event.id, exc_info=exc)
            try:
                result = (
                    service.events()
                    .update(
                        calendarId=cal_id,
                        eventId=event.external_event_id,
                        body=body,
                    )
                    .execute()
                )
            except HttpError as exc:
                if exc.resp is not None and exc.resp.status in (409, 412):
                    raise GoogleEventConflict("Google event was changed remotely.")
                logger.exception("Failed to push updated event %s to Google", event.id, exc_info=exc)
                return ""
            except Exception as exc:
                logger.exception("Failed to push updated event %s to Google", event.id, exc_info=exc)
                return ""
            if not event.external_calendar_id:
                event.external_calendar_id = cal_id
            event.external_etag = result.get("etag")
            updated_str = result.get("updated")
            if updated_str:
                try:
                    event.external_updated = datetime.datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                except Exception:
                    event.external_updated = None
            event.save(update_fields=["external_calendar_id", "external_etag", "external_updated"])
            return event.external_event_id
        return self.push_created_event(event)

    def push_events(self) -> dict:
        """
        Push local (non-external) events on Google calendars up to Google.
        Inserts events without external_event_id; updates events with an existing external_event_id.
        """
        creds = self._load_credentials()
        if not creds:
            raise ValueError("Google credentials not found. Connect first.")

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        calendars = Calendar.objects.filter(user=self.user, provider="google", writable=True)
        inserted = 0
        updated = 0

        for cal in calendars:
            cal_id = cal.external_id or "primary"
            events_qs = Event.objects.filter(
                calendar=cal,
                source__in=["manual", "task"],  # avoid pushing imported external events
            )
            for ev in events_qs:
                if not self._should_push(ev):
                    continue
                body = self._build_event_body(ev)
                try:
                    if ev.external_event_id:
                        service.events().update(
                            calendarId=cal_id,
                            eventId=ev.external_event_id,
                            body=body,
                        ).execute()
                        updated += 1
                    else:
                        result = service.events().insert(
                            calendarId=cal_id,
                            body=body,
                        ).execute()
                        ev.external_event_id = result.get("id")
                        ev.external_calendar_id = cal_id
                        ev.save(update_fields=["external_event_id", "external_calendar_id"])
                        inserted += 1
                except HttpError as exc:
                    if exc.resp is not None and exc.resp.status in (409, 412):
                        logger.warning("Conflict pushing event %s to Google", ev.id)
                    else:
                        logger.exception("Failed to push event %s to Google", ev.id, exc_info=exc)
                except Exception as exc:
                    logger.exception("Failed to push event %s to Google", ev.id, exc_info=exc)

        return {"inserted": inserted, "updated": updated}

    @staticmethod
    def _creds_to_dict(creds: Credentials) -> dict:
        return {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "scopes": creds.scopes,
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
        }
