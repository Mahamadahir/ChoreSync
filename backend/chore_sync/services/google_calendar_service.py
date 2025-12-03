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
from google.auth.exceptions import RefreshError

from chore_sync.models import ExternalCredential, Calendar, Event

logger = logging.getLogger(__name__)


GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]


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
                    },
                )
                count += 1
            page_token = events_result.get("nextPageToken")
            if not page_token:
                break
        return count

    @staticmethod
    def _creds_to_dict(creds: Credentials) -> dict:
        return {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "scopes": creds.scopes,
            "expiry": creds.expiry.isoformat() if creds.expiry else None,
        }
