from __future__ import annotations

import datetime
import logging
from typing import Optional

from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from chore_sync.models import ExternalCredential, Calendar, Event

logger = logging.getLogger(__name__)


GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
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

    def sync_events(self) -> int:
        creds = self._load_credentials()
        if not creds:
            raise ValueError("Google credentials not found. Connect first.")
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        calendar_id = "primary"
        # Pull the full history; pagination will walk through everything until nextPageToken is empty.
        time_min = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc).isoformat()

        cal, _ = Calendar.objects.get_or_create(
            user=self.user,
            provider="google",
            external_id="primary",
            defaults={"name": "Google Calendar (Primary)", "include_in_availability": True},
        )
        count = 0
        page_token = None
        while True:
            events_result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    singleEvents=True,
                    orderBy="startTime",
                    timeMin=time_min,
                    maxResults=500,
                    pageToken=page_token,
                )
                .execute()
            )
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
                Event.objects.update_or_create(
                    external_event_id=item.get("id"),
                    calendar=cal,
                    defaults={
                        "title": item.get("summary", "(no title)"),
                        "description": item.get("description", "") or "",
                        "start": start_dt,
                        "end": end_dt,
                        "is_all_day": is_all_day,
                        "blocks_availability": True,
                        "source": "external",
                        "status": item.get("status", "confirmed"),
                        "external_calendar_id": calendar_id,
                        "external_etag": item.get("etag"),
                        "external_updated": updated_dt,
                    },
                )
                count += 1
            page_token = events_result.get("nextPageToken")
            if not page_token:
                break
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

    def push_created_event(self, event: Event) -> str:
        """
        Push a single locally-created event to Google. Only applies to google calendars.
        Returns the external_event_id that was stored.
        """
        if event.calendar.provider != "google":
            return ""
        creds = self._load_credentials()
        if not creds:
            raise ValueError("Google credentials not found. Connect first.")
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        cal_id = event.calendar.external_id or "primary"
        body = self._build_event_body(event)
        result = service.events().insert(calendarId=cal_id, body=body).execute()
        external_id = result.get("id")
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
        if event.calendar.provider != "google":
            return ""
        creds = self._load_credentials()
        if not creds:
            raise ValueError("Google credentials not found. Connect first.")
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        cal_id = event.calendar.external_id or "primary"
        body = self._build_event_body(event)
        if event.external_event_id:
            # Fetch remote etag to detect conflicts before updating
            remote = service.events().get(calendarId=cal_id, eventId=event.external_event_id).execute()
            remote_etag = remote.get("etag")
            if event.external_etag and remote_etag and remote_etag != event.external_etag:
                raise GoogleEventConflict("Google event was changed remotely.")
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
                raise
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

        calendars = Calendar.objects.filter(user=self.user, provider="google")
        inserted = 0
        updated = 0

        for cal in calendars:
            cal_id = cal.external_id or "primary"
            events_qs = Event.objects.filter(
                calendar=cal,
                source__in=["manual", "task"],  # avoid pushing imported external events
            )
            for ev in events_qs:
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
                except Exception:
                    # Skip failures but continue with others
                    continue

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
