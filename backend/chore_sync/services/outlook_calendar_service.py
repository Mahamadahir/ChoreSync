"""Microsoft Outlook / Graph calendar service for ChoreSync."""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timezone as dt_timezone
from typing import List, Optional
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from chore_sync.models import Calendar, Event, ExternalCredential, OutlookCalendarSync

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPES = ["Calendars.ReadWrite", "offline_access", "User.Read"]


class OutlookCalendarService:
    def __init__(self, user):
        self.user = user
        self.client_id = getattr(settings, "MICROSOFT_CLIENT_ID", "")
        self.client_secret = getattr(settings, "MICROSOFT_CLIENT_SECRET", "")
        self.redirect_uri = getattr(settings, "OUTLOOK_OAUTH_REDIRECT_URI", "")
        self.tenant = getattr(settings, "MICROSOFT_TENANT_ID", "common")
        if not self.client_id or not self.client_secret:
            raise ValueError("Microsoft OAuth is not configured.")

    # ------------------------------------------------------------------ #
    #  OAuth helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pkce_pair() -> tuple[str, str]:
        code_verifier = secrets.token_urlsafe(43)
        digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return code_verifier, code_challenge

    def build_auth_url(self, mobile: bool = False) -> str:
        """Return auth_url with user_id + PKCE verifier embedded in a signed state param.

        The state param carries everything the callback needs so it does not depend
        on the browser session being present (cross-site redirects can drop cookies).
        Pass mobile=True to have the callback redirect to the app URI instead of the web frontend.
        """
        from django.core import signing
        code_verifier, code_challenge = self._pkce_pair()
        # Sign {user_id, verifier, mobile} so it can't be forged; 10-minute expiry
        state = signing.dumps(
            {"uid": str(self.user.id), "cv": code_verifier, "mobile": mobile},
            salt="outlook_oauth",
            compress=True,
        )
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": " ".join(GRAPH_SCOPES),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
            "prompt": "consent",
        }
        base = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/authorize"
        return f"{base}?{urlencode(params)}"

    @staticmethod
    def unsign_state(state: str) -> tuple[str, str, bool]:
        """Verify and decode the signed state param. Returns (user_id, code_verifier, is_mobile).
        Raises django.core.signing.BadSignature on tamper or expiry (10 min).
        """
        from django.core import signing
        data = signing.loads(state, salt="outlook_oauth", max_age=600)
        return data["uid"], data["cv"], bool(data.get("mobile", False))

    def exchange_code(self, code: str, code_verifier: str | None = None) -> ExternalCredential:
        """Exchange the auth code for tokens and persist them."""
        token_url = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
            "scope": " ".join(GRAPH_SCOPES),
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        logger.info("exchange_code: posting to token endpoint for user=%s", self.user.id)
        resp = requests.post(token_url, data=data, timeout=15)
        if not resp.ok:
            logger.error("exchange_code: token exchange failed %s — %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        tokens = resp.json()
        logger.info(
            "exchange_code: token exchange OK — has_access_token=%s has_refresh_token=%s expires_in=%s scopes=%s",
            bool(tokens.get("access_token")),
            bool(tokens.get("refresh_token")),
            tokens.get("expires_in"),
            tokens.get("scope", ""),
        )

        # Fetch user email from Graph
        account_email = None
        try:
            me_resp = requests.get(
                f"{GRAPH_BASE}/me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=10,
            )
            if me_resp.ok:
                account_email = me_resp.json().get("mail") or me_resp.json().get("userPrincipalName")
                logger.info("exchange_code: Graph /me account_email=%s", account_email)
            else:
                logger.warning("exchange_code: Graph /me failed %s", me_resp.status_code)
        except Exception as e:
            logger.warning("exchange_code: Graph /me exception: %s", e)

        expires_in = tokens.get("expires_in", 3600)
        expires_at = timezone.now() + __import__("datetime").timedelta(seconds=expires_in)

        # Use the full unique_together key (user, provider, account_email) so we
        # correctly find/update the SSO credential when account_email matches, or
        # create a calendar-specific credential when it doesn't (or email is None).
        cred, created = ExternalCredential.objects.update_or_create(
            user=self.user,
            provider="microsoft",
            account_email=account_email,
            defaults={
                "secret": {
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens.get("refresh_token"),
                    "expires_at": expires_at.isoformat(),
                    "scope": tokens.get("scope", ""),
                },
                "expires_at": expires_at,
            },
        )
        logger.info(
            "exchange_code: credential %s (id=%s) — expires_at=%s has_access_token=%s",
            "created" if created else "updated",
            cred.id,
            cred.expires_at,
            bool((cred.secret or {}).get("access_token")),
        )

        # Ensure a Calendar row exists for this credential
        cal, _ = Calendar.objects.update_or_create(
            user=self.user,
            provider="microsoft",
            external_id="primary",
            defaults={
                "name": "Outlook Calendar (Primary)",
                "credential": cred,
                "include_in_availability": True,
            },
        )
        OutlookCalendarSync.objects.get_or_create(calendar=cal)
        return cred

    def _get_access_token(self) -> str:
        """Return a valid access token, refreshing if needed."""
        # Filter to credentials that have an expires_at — SSO-only credentials
        # (secret={"sub": ...}) never have expires_at and cannot be used for API calls.
        cred = (
            ExternalCredential.objects.filter(
                user=self.user,
                provider="microsoft",
                expires_at__isnull=False,
            )
            .order_by("-last_refreshed_at")
            .first()
        )
        if not cred:
            raise ValueError("Microsoft credentials not found. Connect Outlook first.")

        data = cred.secret or {}
        logger.debug(
            "_get_access_token: user=%s cred.id=%s account_email=%s "
            "has_access_token=%s has_refresh_token=%s has_expires_at=%s",
            self.user.id, cred.id, cred.account_email,
            bool(data.get("access_token")),
            bool(data.get("refresh_token")),
            bool(data.get("expires_at")),
        )
        # Check expiry (with 60s buffer)
        expires_at_str = data.get("expires_at")
        if expires_at_str:
            try:
                exp = datetime.fromisoformat(expires_at_str)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=dt_timezone.utc)
                remaining = (exp - timezone.now()).total_seconds()
                logger.debug("_get_access_token: token remaining=%ss", int(remaining))
                if remaining > 60:
                    return data["access_token"]
            except (ValueError, KeyError) as e:
                logger.warning("_get_access_token: failed to parse/return token: %s", e)

        # Token is expired (or no expires_at) — try to refresh
        refresh_token = data.get("refresh_token")
        if not refresh_token:
            # If we somehow still have a non-expired access_token, use it rather than failing.
            # This handles the edge case where Microsoft didn't return a refresh_token.
            access_token = data.get("access_token")
            if access_token:
                logger.warning(
                    "_get_access_token: no refresh token for user=%s — using existing access token",
                    self.user.id,
                )
                return access_token
            raise ValueError("Microsoft refresh token missing. Please reconnect Outlook.")

        token_url = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        resp = requests.post(
            token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(GRAPH_SCOPES),
            },
            timeout=15,
        )
        resp.raise_for_status()
        tokens = resp.json()
        expires_in = tokens.get("expires_in", 3600)
        new_expires_at = timezone.now() + __import__("datetime").timedelta(seconds=expires_in)
        new_secret = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", refresh_token),
            "expires_at": new_expires_at.isoformat(),
            "scope": tokens.get("scope", data.get("scope", "")),
        }
        cred.mark_refreshed(new_secret, new_expires_at)
        return tokens["access_token"]

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    def _paginate(self, url: str) -> list[dict]:
        """Follow @odata.nextLink pagination, return all items."""
        items = []
        while url:
            resp = requests.get(url, headers=self._headers(), timeout=15)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                raise ValueError(f"Microsoft Graph throttled. Retry after {retry_after}s.")
            resp.raise_for_status()
            body = resp.json()
            items.extend(body.get("value", []))
            url = body.get("@odata.nextLink")
        return items

    # ------------------------------------------------------------------ #
    #  Calendar listing
    # ------------------------------------------------------------------ #

    def list_calendars(self) -> List[dict]:
        """Return normalized list of Outlook calendars for this user."""
        items = self._paginate(f"{GRAPH_BASE}/me/calendars?$top=50")
        return [
            {
                "id": c["id"],
                "name": c.get("name", "(untitled)"),
                "color": c.get("color", ""),
                "is_default": c.get("isDefaultCalendar", False),
                "can_edit": c.get("canEdit", False),
            }
            for c in items
        ]

    # ------------------------------------------------------------------ #
    #  Sync events
    # ------------------------------------------------------------------ #

    def sync_events(self, calendar: Optional[Calendar] = None) -> int:
        """Pull new/changed/deleted events from Outlook via delta query. Returns count of changes."""
        if calendar is None:
            calendar = Calendar.objects.filter(user=self.user, provider="microsoft").first()
        if not calendar:
            return 0

        sync_state, _ = OutlookCalendarSync.objects.get_or_create(calendar=calendar)
        count = 0

        if sync_state.delta_link:
            url = sync_state.delta_link
        else:
            # Initial sync — get all events within sync window
            from django.utils.timezone import now
            import datetime as dt
            start = (now() - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            end = (now() + dt.timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
            cal_id = calendar.external_id or "primary"
            url = (
                f"{GRAPH_BASE}/me/calendars/{cal_id}/events/delta"
                f"?startDateTime={start}&endDateTime={end}&$top=50"
            )

        items: list[dict] = []
        new_delta_link: str | None = None

        while url:
            resp = requests.get(url, headers=self._headers(), timeout=15)
            if resp.status_code == 429:
                raise ValueError("Microsoft Graph throttled. Try again later.")
            resp.raise_for_status()
            body = resp.json()
            items.extend(body.get("value", []))
            url = body.get("@odata.nextLink")
            if not url:
                new_delta_link = body.get("@odata.deltaLink")

        for item in items:
            count += 1
            removed = item.get("@removed")
            ext_id = item["id"]

            if removed:
                Event.objects.filter(calendar=calendar, external_event_id=ext_id).update(
                    source="external"
                )
                continue

            start_raw = item.get("start", {})
            end_raw = item.get("end", {})
            start_str = start_raw.get("dateTime") or start_raw.get("date")
            end_str = end_raw.get("dateTime") or end_raw.get("date")

            Event.objects.update_or_create(
                calendar=calendar,
                external_event_id=ext_id,
                defaults={
                    "title": item.get("subject", "(no title)"),
                    "description": item.get("bodyPreview", ""),
                    "start": self._parse_dt(start_str),
                    "end": self._parse_dt(end_str),
                    "is_all_day": item.get("isAllDay", False),
                    "blocks_availability": not item.get("showAs", "busy") == "free",
                    "source": "external",
                },
            )

        if new_delta_link:
            sync_state.delta_link = new_delta_link
            sync_state.save(update_fields=["delta_link"])

        calendar.last_synced_at = timezone.now()
        calendar.save(update_fields=["last_synced_at"])
        return count

    # ------------------------------------------------------------------ #
    #  Graph webhook subscription
    # ------------------------------------------------------------------ #

    def renew_subscription(self, calendar: Calendar) -> None:
        """Create or extend a Graph change-notification subscription (max 3-day expiry).

        If a subscription_id already exists on the sync state, PATCHes it to extend.
        Otherwise POSTs a new subscription.
        BACKEND_BASE_URL must be publicly reachable by Microsoft for webhooks to fire.
        """
        from datetime import timedelta
        sync_state, _ = OutlookCalendarSync.objects.get_or_create(calendar=calendar)
        expiry = timezone.now() + timedelta(days=3)
        webhook_url = f"{getattr(settings, 'BACKEND_BASE_URL', 'http://localhost:8000')}/api/calendar/outlook/webhook/"
        secret = getattr(settings, "OUTLOOK_WEBHOOK_SECRET", "")

        if sync_state.subscription_id:
            # Extend existing subscription
            resp = requests.patch(
                f"{GRAPH_BASE}/subscriptions/{sync_state.subscription_id}",
                json={"expirationDateTime": expiry.isoformat()},
                headers=self._headers(),
                timeout=15,
            )
            if resp.status_code == 404:
                # Subscription expired/deleted — create fresh
                sync_state.subscription_id = None
                sync_state.save(update_fields=["subscription_id"])
                self.renew_subscription(calendar)
                return
            resp.raise_for_status()
        else:
            payload = {
                "changeType": "created,updated,deleted",
                "notificationUrl": webhook_url,
                "resource": f"/me/calendars/{calendar.external_id}/events",
                "expirationDateTime": expiry.isoformat(),
                "clientState": secret,
            }
            resp = requests.post(
                f"{GRAPH_BASE}/subscriptions",
                json=payload,
                headers=self._headers(),
                timeout=15,
            )
            resp.raise_for_status()
            sync_state.subscription_id = resp.json()["id"]

        sync_state.subscription_expires_at = expiry
        sync_state.save(update_fields=["subscription_id", "subscription_expires_at"])

    # ------------------------------------------------------------------ #
    #  Write-back helpers
    # ------------------------------------------------------------------ #

    def push_created_event(self, event: Event) -> None:
        """Create an event in Outlook for a task writeback."""
        cal = event.calendar
        if not cal or cal.provider != "microsoft":
            return
        cal_id = cal.external_id or "primary"
        payload = self._event_to_graph(event)
        resp = requests.post(
            f"{GRAPH_BASE}/me/calendars/{cal_id}/events",
            json=payload,
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        event.external_event_id = data["id"]
        event.save(update_fields=["external_event_id"])

    def push_updated_event(self, event: Event) -> None:
        if not event.external_event_id or not event.calendar or event.calendar.provider != "microsoft":
            return
        cal_id = event.calendar.external_id or "primary"
        resp = requests.patch(
            f"{GRAPH_BASE}/me/calendars/{cal_id}/events/{event.external_event_id}",
            json=self._event_to_graph(event),
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()

    def push_deleted_event(self, event: Event) -> None:
        if not event.external_event_id or not event.calendar or event.calendar.provider != "microsoft":
            return
        cal_id = event.calendar.external_id or "primary"
        requests.delete(
            f"{GRAPH_BASE}/me/calendars/{cal_id}/events/{event.external_event_id}",
            headers=self._headers(),
            timeout=15,
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _event_to_graph(event: Event) -> dict:
        def _fmt(dt) -> dict:
            if dt:
                return {"dateTime": dt.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": "UTC"}
            return {}

        return {
            "subject": event.title,
            "body": {"contentType": "text", "content": event.description or ""},
            "start": _fmt(event.start),
            "end": _fmt(event.end),
            "isAllDay": event.is_all_day,
        }

    @staticmethod
    def _parse_dt(value: str | None):
        if not value:
            return None
        import datetime as dt
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                naive = dt.datetime.strptime(value.rstrip("Z"), fmt)
                return naive.replace(tzinfo=dt_timezone.utc)
            except ValueError:
                continue
        return None
