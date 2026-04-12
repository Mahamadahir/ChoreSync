"""API views for Microsoft Outlook calendar integration."""
from __future__ import annotations

import logging

from django.conf import settings
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from chore_sync.models import Calendar, OutlookCalendarSync
from chore_sync.services.outlook_calendar_service import OutlookCalendarService

logger = logging.getLogger(__name__)


class OutlookCalendarAuthURLAPIView(APIView):
    """GET /api/calendar/outlook/auth-url/ — returns Microsoft OAuth consent URL.

    Accepts ?mobile=true to embed a mobile=True flag in the signed state so the
    callback can redirect back to the app instead of the web frontend.
    """
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from django.core import signing
            mobile = request.query_params.get("mobile") == "true"
            svc = OutlookCalendarService(request.user)
            url = svc.build_auth_url(mobile=mobile)
            logger.info("Outlook auth URL redirect_uri: %s", svc.redirect_uri)
            return Response({"auth_url": url, "redirect_uri": svc.redirect_uri})
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@method_decorator(csrf_exempt, name="dispatch")
class OutlookCalendarCallbackAPIView(APIView):
    """GET /api/calendar/outlook/callback/ — receives Microsoft OAuth redirect.

    This endpoint is intentionally AllowAny: the browser is redirected here by
    Microsoft so there is no guarantee the Django session cookie is present.
    The user is identified via the signed `state` parameter embedded during
    build_auth_url(), which cannot be forged and expires after 10 minutes.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        frontend_url = getattr(settings, "FRONTEND_APP_URL", "http://localhost:5173")
        mobile_redirect_uri = getattr(settings, "MOBILE_CALENDAR_REDIRECT_URI", "choresync://calendar/connected")
        error_param = request.query_params.get("error")
        if error_param:
            logger.warning("Outlook OAuth error from Microsoft: %s — %s",
                           error_param, request.query_params.get("error_description", ""))
            return redirect(f"{frontend_url}/calendar/outlook/select?error=1")

        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            return redirect(f"{frontend_url}/calendar/outlook/select?error=1")

        try:
            from django.core.signing import BadSignature
            from django.contrib.auth import get_user_model
            user_id, code_verifier, is_mobile = OutlookCalendarService.unsign_state(state)
            User = get_user_model()
            user = User.objects.get(pk=user_id)
            svc = OutlookCalendarService(user)
            svc.exchange_code(code, code_verifier=code_verifier)
            if is_mobile:
                return redirect(f"{mobile_redirect_uri}?provider=outlook")
            return redirect(f"{frontend_url}/calendar/outlook/select?connected=1")
        except Exception as exc:
            logger.exception("Outlook callback failed", exc_info=exc)
            return redirect(f"{frontend_url}/calendar/outlook/select?error=1")


class OutlookCalendarListAPIView(APIView):
    """GET /api/calendar/outlook/list/ — list user's Outlook calendars."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            svc = OutlookCalendarService(request.user)
            calendars = svc.list_calendars()
            return Response(calendars)
        except ValueError as exc:
            logger.warning("Outlook list calendars ValueError for user %s: %s", request.user.id, exc)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Failed to list Outlook calendars for user %s", request.user.id, exc_info=exc)
            return Response({"detail": f"Failed to list Outlook calendars: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OutlookCalendarSelectAPIView(APIView):
    """POST /api/calendar/outlook/select/ — save selected Outlook calendars."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Payload: list of {id, name, include_in_availability, writable, is_task_writeback, color, timezone}
        Only one item may have is_task_writeback=true; that calendar will receive task events from ChoreSync.
        """
        items = request.data if isinstance(request.data, list) else []
        if not items:
            return Response({"detail": "No calendars provided."}, status=status.HTTP_400_BAD_REQUEST)

        from chore_sync.models import ExternalCredential
        from chore_sync.tasks import initial_outlook_sync_task
        cred = (
            ExternalCredential.objects.filter(user=request.user, provider="microsoft")
            .order_by("-last_refreshed_at")
            .first()
        )
        if not cred:
            return Response({"detail": "Outlook not connected."}, status=status.HTTP_400_BAD_REQUEST)

        # Determine which calendar (if any) the user wants as their task writeback.
        writeback_ext_id = next(
            (item.get("id") for item in items if item.get("is_task_writeback")),
            None,
        )
        # If no explicit choice, fall back to the first push_enabled calendar.
        if not writeback_ext_id:
            writeback_ext_id = next(
                (item.get("id") for item in items if item.get("writable")),
                None,
            )

        selected_ids = []
        queued_ids = []
        for item in items:
            ext_id = item.get("id")
            if not ext_id:
                continue
            is_writeback = ext_id == writeback_ext_id
            cal, created = Calendar.objects.update_or_create(
                user=request.user,
                provider="microsoft",
                external_id=ext_id,
                defaults={
                    "name": item.get("name", "Outlook Calendar"),
                    "credential": cred,
                    "include_in_availability": item.get("include_in_availability", True),
                    "push_enabled": item.get("writable", False),
                    "is_task_writeback": is_writeback,
                    "color": item.get("color") or None,
                    "timezone": item.get("timezone") or "UTC",
                },
            )
            OutlookCalendarSync.objects.get_or_create(calendar=cal)
            selected_ids.append(cal.external_id)

            if created or not cal.last_synced_at:
                initial_outlook_sync_task.apply_async(
                    args=[cal.id],
                    queue="calendar_sync",
                )
                queued_ids.append(cal.external_id)

        # If the user designated an Outlook calendar as task writeback, clear is_task_writeback
        # from all other calendars for this user (including the internal one).
        if writeback_ext_id:
            Calendar.objects.filter(
                user=request.user,
            ).exclude(
                provider="microsoft",
                external_id=writeback_ext_id,
            ).update(is_task_writeback=False)

        return Response({
            "detail": "Outlook calendars saved.",
            "selected": selected_ids,
            "syncing": queued_ids,
        })


class OutlookCalendarSyncAPIView(APIView):
    """POST /api/calendar/outlook/sync/ — trigger an incremental sync."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            svc = OutlookCalendarService(request.user)
            count = svc.sync_events()
            return Response({"detail": f"Synced {count} events from Outlook."})
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Outlook sync failed", exc_info=exc)
            return Response({"detail": "Outlook sync failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name="dispatch")
class OutlookCalendarWebhookAPIView(APIView):
    """POST /api/calendar/outlook/webhook/ — receive Microsoft Graph change notifications.

    Microsoft requires this endpoint to:
    1. Respond to validation pings (validationToken in query string) with 200 + plain text token.
    2. Validate clientState on all notification payloads.
    3. Respond within 3 seconds (actual sync is queued to Celery).
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        # Validation handshake: Microsoft sends ?validationToken=... to confirm the endpoint
        validation_token = request.query_params.get("validationToken")
        if validation_token:
            from django.http import HttpResponse
            return HttpResponse(validation_token, content_type="text/plain", status=200)

        # Validate clientState to reject spoofed notifications
        expected_secret = getattr(settings, "OUTLOOK_WEBHOOK_SECRET", "")
        notifications = request.data.get("value", [])

        if expected_secret:
            for notif in notifications:
                if notif.get("clientState") != expected_secret:
                    logger.warning("Outlook webhook: clientState mismatch — ignoring notification")
                    return Response(status=status.HTTP_401_UNAUTHORIZED)

        # Queue an incremental sync for each affected calendar
        from chore_sync.tasks import initial_outlook_sync_task

        for notif in notifications:
            # resource looks like "/me/calendars/<calendarId>/events"
            resource = notif.get("resource", "")
            # Try to find the matching Calendar row by external_id
            parts = resource.split("/")
            # Expected: ['', 'me', 'calendars', '<id>', 'events']
            if len(parts) >= 4 and parts[2] == "calendars":
                ext_cal_id = parts[3]
                cal = Calendar.objects.filter(
                    provider="microsoft",
                    external_id=ext_cal_id,
                ).first()
                if cal:
                    initial_outlook_sync_task.apply_async(
                        args=[cal.id],
                        queue="calendar_sync",
                    )
                    logger.debug("Outlook webhook: queued sync for calendar %s", cal.id)

        # Microsoft expects a quick 202 Accepted
        return Response(status=status.HTTP_202_ACCEPTED)
