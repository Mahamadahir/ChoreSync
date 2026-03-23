"""API views for Microsoft Outlook calendar integration."""
from __future__ import annotations

import logging

from django.conf import settings
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from chore_sync.api.views import CsrfExemptSessionAuthentication
from chore_sync.models import Calendar, OutlookCalendarSync
from chore_sync.services.outlook_calendar_service import OutlookCalendarService

logger = logging.getLogger(__name__)


class OutlookCalendarAuthURLAPIView(APIView):
    """GET /api/calendar/outlook/auth-url/ — returns Microsoft OAuth consent URL."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            svc = OutlookCalendarService(request.user)
            url, code_verifier = svc.build_auth_url()
            request.session["outlook_pkce_verifier"] = code_verifier
            return Response({"auth_url": url})
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@method_decorator(csrf_exempt, name="dispatch")
class OutlookCalendarCallbackAPIView(APIView):
    """GET /api/calendar/outlook/callback/ — receives Microsoft OAuth redirect."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = request.query_params.get("code")
        if not code:
            return Response({"detail": "Missing code"}, status=status.HTTP_400_BAD_REQUEST)
        frontend_url = getattr(settings, "FRONTEND_APP_URL", "http://localhost:5173")
        try:
            svc = OutlookCalendarService(request.user)
            code_verifier = request.session.pop("outlook_pkce_verifier", None)
            svc.exchange_code(code, code_verifier=code_verifier)
            return redirect(f"{frontend_url}/calendar/outlook/select?connected=1")
        except Exception as exc:
            logger.exception("Outlook callback failed", exc_info=exc)
            return redirect(f"{frontend_url}/calendar/outlook/select?error=1")


class OutlookCalendarListAPIView(APIView):
    """GET /api/calendar/outlook/list/ — list user's Outlook calendars."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            svc = OutlookCalendarService(request.user)
            calendars = svc.list_calendars()
            return Response(calendars)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Failed to list Outlook calendars", exc_info=exc)
            return Response({"detail": "Failed to list Outlook calendars."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OutlookCalendarSelectAPIView(APIView):
    """POST /api/calendar/outlook/select/ — save selected Outlook calendars."""
    authentication_classes = [CsrfExemptSessionAuthentication]
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
    authentication_classes = [CsrfExemptSessionAuthentication]
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
