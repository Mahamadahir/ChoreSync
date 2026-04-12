from __future__ import annotations

from rest_framework import status, renderers
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

import logging
from django.shortcuts import redirect

from chore_sync.api.serializers import (
    SignupSerializer,
    LoginSerializer,
    ResendVerificationSerializer,
    VerifyEmailSerializer,
    UpdateEmailSerializer,
    ProfileSerializer,
    ForgotPasswordRequestSerializer,
    ResetPasswordSerializer,
    ChangePasswordSerializer,
    GoogleLoginSerializer,
    MicrosoftLoginSerializer,
    EventSerializer,
    EventCreateSerializer,
    GoogleCalendarSelectionSerializer,
)
from chore_sync.services.auth_service import AccountService
from chore_sync.services.google_calendar_service import GoogleCalendarService, GoogleEventConflict
from django.contrib.auth import get_user_model
from chore_sync.dtos.user_dtos import UserDTO
from chore_sync.domain_errors import (
    InvalidEmail,
    EmailAlreadyTaken,
    UsernameAlreadyTaken,
    WeakPassword,
    RegistrationError,
    VerificationTokenInvalid,
    VerificationTokenUsed,
    VerificationTokenExpired,
    InvalidCredentials,
    InactiveAccount,
)
from django.contrib.auth import login, logout
from django.conf import settings
from django.utils.dateparse import parse_datetime
from googleapiclient.discovery import build as google_build
from googleapiclient.errors import HttpError
from django.http import StreamingHttpResponse
import json
import queue
from chore_sync import sse

User = get_user_model()
logger = logging.getLogger(__name__)


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session auth with CSRF enforcement re-enabled.

    DRF's APIView.as_view() marks all views as csrf_exempt at the Django middleware
    level, so CSRF protection for session-authenticated requests relies entirely on
    SessionAuthentication.enforce_csrf().  This class re-enables that check so that
    cookie-based (Vue web) requests must supply a valid X-CSRFToken header.

    JWT-authenticated (mobile) requests are unaffected — enforce_csrf() is only
    called when session auth is the authenticating class for the request.
    """


class SSERenderer(renderers.BaseRenderer):
    media_type = "text/event-stream"
    format = "sse"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


def user_dto_to_dict(dto: UserDTO) -> dict:
    return {
        "id": dto.id,
        "username": dto.username,
        "email": dto.email,
        "is_active": dto.is_active,
        "email_verified": getattr(dto, "email_verified", False),
        "first_name": getattr(dto, "first_name", ""),
        "last_name": getattr(dto, "last_name", ""),
    }


@method_decorator(csrf_exempt, name="dispatch")
class SignupAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        svc = AccountService()
        try:
            user_dto = svc.register_user(**serializer.validated_data)
        except (InvalidEmail, EmailAlreadyTaken, UsernameAlreadyTaken, WeakPassword) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RegistrationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {
                **user_dto_to_dict(user_dto),
                "message": "User registered. Check email for verification.",
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        svc = AccountService()
        try:
            user, user_dto = svc.authenticate(
                identifier=serializer.validated_data["identifier"],
                password=serializer.validated_data["password"],
            )
        except InvalidCredentials as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        except InactiveAccount as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        login(request, user)  # issue session cookie
        return Response(
            {
                "email_verified": getattr(user_dto, "email_verified", False),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "email": user.email,
                "detail": "Login successful.",
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def post(self, request):
        logout(request)
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class ResendVerificationAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        svc = AccountService()
        try:
            svc.send_verification_email_with_cooldown(email)
        except (InvalidEmail, RegistrationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            # Do not reveal account existence; respond generically.
            return Response(
                {"detail": "If this account exists, a verification email will be sent."},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"detail": "If this account exists, a verification email will be sent."},
            status=status.HTTP_200_OK,
        )

@method_decorator(csrf_exempt, name="dispatch")
class VerifyEmailAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        svc = AccountService()
        try:
            user = svc.verify_email_token(token)
        except VerificationTokenInvalid as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except VerificationTokenUsed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except VerificationTokenExpired as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_410_GONE)
        return Response(
            {
                "detail": "Email verified.",
                **user_dto_to_dict(user),
            },
            status=status.HTTP_200_OK,
        )

@method_decorator(csrf_exempt, name="dispatch")
class UpdateEmailAPIView(APIView):
    """
    Allow updating email during verification flow: provided a valid token and new email,
    update the user's email (if not taken), reset verification, and send a new token.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = UpdateEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_value = serializer.validated_data["token"]
        new_email = serializer.validated_data["email"]
        svc = AccountService()
        try:
            user_dto = svc.update_email_and_resend_verification(token_value, new_email)
        except VerificationTokenInvalid as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except VerificationTokenUsed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except VerificationTokenExpired as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_410_GONE)
        except (InvalidEmail, EmailAlreadyTaken, RegistrationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Email updated. Check your inbox for a new verification link.",
                **user_dto_to_dict(user_dto),
            },
            status=status.HTTP_200_OK,
        )

@method_decorator(csrf_exempt, name="dispatch")
class ProfileAPIView(APIView):
    """
    Basic profile retrieval/update. Uses session auth if present; otherwise returns 401.
    """

    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
        user = request.user
        dto = UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            email_verified=getattr(user, "email_verified", False),
        )
        return Response(
            {
                **user_dto_to_dict(dto),
                "username": user.username,
                "timezone": getattr(user, "timezone", ""),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "avatar_url": user.get_avatar_url(request),
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = ProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        svc = AccountService()
        try:
            user_dto = svc.update_profile(
                request.user,
                username=data.get("username"),
                email=data.get("email"),
                timezone=data.get("timezone"),
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
            )
        except (InvalidEmail, EmailAlreadyTaken, RegistrationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Profile updated.",
                **user_dto_to_dict(user_dto),
                "username": user_dto.username,
                "timezone": getattr(request.user, "timezone", ""),
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
                "avatar_url": request.user.get_avatar_url(request),
            },
            status=status.HTTP_200_OK,
        )


_AVATAR_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_AVATAR_ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/heic'}


class AvatarUploadAPIView(APIView):
    """POST /api/users/me/avatar/ — upload or replace profile photo."""
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        photo = request.FILES.get('avatar')
        if photo is None:
            return Response({'detail': 'avatar file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if photo.size > _AVATAR_MAX_BYTES:
            return Response({'detail': 'File too large. Maximum 5 MB.'}, status=status.HTTP_400_BAD_REQUEST)
        if photo.content_type not in _AVATAR_ALLOWED_TYPES:
            return Response(
                {'detail': f"Unsupported type '{photo.content_type}'. Use JPEG, PNG, WebP, GIF, or HEIC."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        # Delete old file to avoid orphaned uploads
        if user.avatar:
            user.avatar.delete(save=False)
        user.avatar = photo
        user.save(update_fields=['avatar'])
        return Response({'avatar_url': user.get_avatar_url(request)}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class ForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ForgotPasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        svc = AccountService()
        try:
            svc.send_password_reset(email)
        except User.DoesNotExist:
            # Do not reveal existence; respond generically
            return Response({"detail": "If this account exists, a reset link was sent."}, status=status.HTTP_200_OK)
        except InactiveAccount as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidEmail as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "If this account exists, a reset link was sent."}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]
        svc = AccountService()
        try:
            user_dto = svc.reset_password(token, new_password)
        except VerificationTokenInvalid as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except VerificationTokenUsed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except VerificationTokenExpired as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_410_GONE)
        except WeakPassword as exc:
            return Response({"detail": exc.messages if hasattr(exc, 'messages') else str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Password reset successful.",
                "email_verified": getattr(user_dto, "email_verified", False),
                "is_active": user_dto.is_active,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        current_password = serializer.validated_data.get("current_password", "")
        new_password = serializer.validated_data["new_password"]
        svc = AccountService()
        try:
            svc.change_password(request.user, current_password, new_password)
        except InvalidCredentials as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except WeakPassword as exc:
            return Response({"detail": exc.messages if hasattr(exc, 'messages') else str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class GoogleLoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        svc = AccountService()
        try:
            user, user_dto = svc.sign_in_with_google(id_token=serializer.validated_data["id_token"])
        except (InvalidCredentials, InvalidEmail, RegistrationError, InactiveAccount) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        login(request, user)
        return Response(
            {
                "detail": "Login via Google successful.",
                "username": user_dto.username,
                "email": user_dto.email,
                "email_verified": getattr(user_dto, "email_verified", False),
                "is_active": user_dto.is_active,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class MicrosoftLoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not settings.MICROSOFT_CLIENT_ID:
            return Response({"detail": "Microsoft Sign-In is not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        serializer = MicrosoftLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        svc = AccountService()
        try:
            user, user_dto = svc.sign_in_with_microsoft(id_token=serializer.validated_data["id_token"])
        except (InvalidCredentials, InvalidEmail, RegistrationError, InactiveAccount) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        login(request, user)
        return Response(
            {
                "detail": "Login via Microsoft successful.",
                "username": user_dto.username,
                "email": user_dto.email,
                "email_verified": getattr(user_dto, "email_verified", False),
                "is_active": user_dto.is_active,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            status=status.HTTP_200_OK,
        )


class EventsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)

        start_param = request.query_params.get("start")
        end_param = request.query_params.get("end")
        from chore_sync.models import Event  # local import to avoid circular references

        qs = Event.objects.filter(calendar__user=request.user)
        if start_param:
            start_dt = parse_datetime(start_param)
            if start_dt:
                qs = qs.filter(end__gte=start_dt)
        if end_param:
            end_dt = parse_datetime(end_param)
            if end_dt:
                qs = qs.filter(start__lte=end_dt)

        data = [
            {
                "id": ev.id,
                "title": ev.title,
                "description": ev.description,
                "start": ev.start,
                "end": ev.end,
                "is_all_day": ev.is_all_day,
                "blocks_availability": ev.blocks_availability,
                "source": ev.source,
                "calendar_id": ev.calendar_id,
                "calendar_name": ev.calendar.name,
                "calendar_color": ev.calendar.color,
            }
            for ev in qs.select_related("calendar")
        ]

        serializer = EventSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = EventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from chore_sync.models import Event, Calendar  # local import to avoid circular references

        cal_id = serializer.validated_data.get("calendar_id")
        calendar = None
        if cal_id:
            calendar = Calendar.objects.filter(pk=cal_id, user=request.user).first()
        if calendar is None:
            calendar = Calendar.objects.filter(user=request.user, provider="internal").first()
        if calendar is None:
            calendar = Calendar.objects.filter(user=request.user).first()
        if calendar is None:
            return Response({"detail": "No calendar available for this user."}, status=status.HTTP_400_BAD_REQUEST)

        ev = Event.objects.create(
            calendar=calendar,
            title=serializer.validated_data["title"],
            description=serializer.validated_data.get("description", ""),
            start=serializer.validated_data["start"],
            end=serializer.validated_data["end"],
            is_all_day=serializer.validated_data.get("is_all_day", False),
            blocks_availability=serializer.validated_data.get("blocks_availability", True),
            source="manual",
        )
        out = {
            "id": ev.id,
            "title": ev.title,
            "description": ev.description,
            "start": ev.start,
            "end": ev.end,
            "is_all_day": ev.is_all_day,
            "blocks_availability": ev.blocks_availability,
            "source": ev.source,
            "calendar_id": ev.calendar_id,
            "calendar_name": ev.calendar.name,
            "calendar_color": ev.calendar.color,
        }
        if calendar.provider == "google" and getattr(calendar, "push_enabled", True):
            try:
                GoogleCalendarService(request.user).push_created_event(ev)
            except GoogleEventConflict:
                return Response(
                    {**out, "detail": "This event changed in Google. Please refresh and retry."},
                    status=status.HTTP_409_CONFLICT,
                )
            except Exception as exc:
                logger.exception("Failed to push new event to Google", exc_info=exc)
        elif calendar.provider == "microsoft" and getattr(calendar, "push_enabled", True):
            try:
                from chore_sync.services.outlook_calendar_service import OutlookCalendarService
                OutlookCalendarService(request.user).push_created_event(ev)
            except Exception as exc:
                logger.exception("Failed to push new event to Outlook", exc_info=exc)
        return Response(out, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class EventDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def patch(self, request, pk: int):
        if not request.user.is_authenticated:
            return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = EventCreateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        from chore_sync.models import Event  # local import
        try:
            ev = Event.objects.select_related("calendar").get(pk=pk, calendar__user=request.user)
        except Event.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        for field in ["title", "description", "start", "end", "is_all_day", "blocks_availability"]:
            if field in serializer.validated_data:
                setattr(ev, field, serializer.validated_data[field])
        ev.save()

        out = {
            "id": ev.id,
            "title": ev.title,
            "description": ev.description,
            "start": ev.start,
            "end": ev.end,
            "is_all_day": ev.is_all_day,
            "blocks_availability": ev.blocks_availability,
            "source": ev.source,
            "calendar_id": ev.calendar_id,
            "calendar_name": ev.calendar.name,
            "calendar_color": ev.calendar.color,
        }
        if ev.calendar.provider == "google" and getattr(ev.calendar, "push_enabled", True):
            try:
                GoogleCalendarService(request.user).push_updated_event(ev)
            except GoogleEventConflict:
                logger.warning("Conflict pushing event %s to Google", ev.id)
                return Response(
                    {**out, "detail": "This event changed in Google. Please refresh and retry."},
                    status=status.HTTP_409_CONFLICT,
                )
            except Exception as exc:
                logger.exception("Failed to push updated event to Google", exc_info=exc)
        elif ev.calendar.provider == "microsoft" and getattr(ev.calendar, "push_enabled", True):
            try:
                from chore_sync.services.outlook_calendar_service import OutlookCalendarService
                OutlookCalendarService(request.user).push_updated_event(ev)
            except Exception as exc:
                logger.exception("Failed to push updated event to Outlook", exc_info=exc)
        return Response(out, status=status.HTTP_200_OK)

    def delete(self, request, pk: int):
        from chore_sync.models import Event
        try:
            ev = Event.objects.select_related("calendar").get(pk=pk, calendar__user=request.user)
        except Event.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if ev.calendar.provider == "google" and ev.external_event_id:
            try:
                svc = GoogleCalendarService(request.user)
                creds = svc._load_credentials()
                if creds:
                    service = google_build("calendar", "v3", credentials=creds, cache_discovery=False)
                    cal_id = ev.calendar.external_id or "primary"
                    service.events().delete(calendarId=cal_id, eventId=ev.external_event_id).execute()
            except Exception as exc:
                logger.warning("Failed to delete Google event %s: %s", ev.external_event_id, exc)
        elif ev.calendar.provider == "microsoft" and ev.external_event_id:
            try:
                from chore_sync.services.outlook_calendar_service import OutlookCalendarService
                OutlookCalendarService(request.user).push_deleted_event(ev)
            except Exception as exc:
                logger.warning("Failed to delete Outlook event %s: %s", ev.external_event_id, exc)
        ev.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name="dispatch")
class GoogleCalendarListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def get(self, request):
        try:
            from chore_sync.models import Calendar as CalendarModel
            svc = GoogleCalendarService(request.user)
            calendars = svc.list_calendars(min_access_role="reader")
            # Annotate each entry with whether a synced Calendar row already exists.
            synced_ids = set(
                CalendarModel.objects.filter(user=request.user, provider="google")
                .exclude(external_id=None)
                .values_list("external_id", flat=True)
            )
            for cal in calendars:
                cal["already_synced"] = cal.get("id") in synced_ids
            return Response(calendars, status=status.HTTP_200_OK)
        except HttpError as exc:
            if exc.resp is not None and exc.resp.status == 403:
                return Response({"detail": "Google permissions are insufficient. Please reconnect and grant calendar access."}, status=status.HTTP_403_FORBIDDEN)
            logger.exception("Failed to list Google calendars", exc_info=exc)
            return Response({"detail": "Failed to list Google calendars."}, status=status.HTTP_502_BAD_GATEWAY)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Failed to list Google calendars", exc_info=exc)
            return Response({"detail": "Failed to list Google calendars."}, status=status.HTTP_502_BAD_GATEWAY)


@method_decorator(csrf_exempt, name="dispatch")
class GoogleCalendarSelectAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def post(self, request):
        serializer = GoogleCalendarSelectionSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        from chore_sync.models import Calendar, ExternalCredential

        selections = serializer.validated_data
        svc = GoogleCalendarService(request.user)
        credential = (
            ExternalCredential.objects.filter(user=request.user, provider="google")
            .order_by("-last_refreshed_at")
            .first()
        )
        from chore_sync.models import GoogleCalendarSync
        from chore_sync.tasks import initial_google_sync_task
        selected_ids = []
        queued_ids = []
        for item in selections:
            defaults = {
                "name": item["name"],
                "include_in_availability": item["include_in_availability"],
                "push_enabled": item["writable"],
            }
            if "color" in item:
                defaults["color"] = item["color"]
            if item.get("timezone"):
                defaults["timezone"] = item["timezone"]
            if credential:
                defaults["credential"] = credential
            cal, created = Calendar.objects.update_or_create(
                user=request.user,
                provider="google",
                external_id=item["id"],
                defaults=defaults,
            )
            # Ensure GoogleCalendarSync row exists; store oauth_writable
            sync_state, _ = GoogleCalendarSync.objects.get_or_create(calendar=cal)
            if sync_state.oauth_writable != item["writable"]:
                sync_state.oauth_writable = item["writable"]
                sync_state.save(update_fields=["oauth_writable"])
            selected_ids.append(cal.external_id)
            # Queue initial full sync only for newly created calendars with no prior sync.
            # Watch channel is registered by the task after sync completes (avoids race).
            if created or not cal.last_synced_at:
                if not sync_state.active_task_id:
                    initial_google_sync_task.apply_async(
                        args=[cal.id],
                        queue='calendar_sync',
                    )
                    queued_ids.append(cal.external_id)
        qs = Calendar.objects.filter(user=request.user, provider="google")
        if selected_ids:
            for cal in qs.exclude(external_id__in=selected_ids):
                cal.include_in_availability = False
                cal.save(update_fields=["include_in_availability"])
                try:
                    svc.stop_watch_channel(cal)
                except Exception:
                    logger.debug("Failed to stop watch for calendar %s", cal.external_id, exc_info=True)
        else:
            for cal in qs:
                cal.include_in_availability = False
                cal.save(update_fields=["include_in_availability"])
                try:
                    svc.stop_watch_channel(cal)
                except Exception:
                    logger.debug("Failed to stop watch for calendar %s", cal.external_id, exc_info=True)
        return Response(
            {
                "detail": "Google calendars updated.",
                "selected": selected_ids,
                "syncing": queued_ids,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class GoogleCalendarWebhookAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from chore_sync.models import GoogleCalendarSync

        # Google sends a sync ping when the watch channel is first registered — just acknowledge it
        resource_state = request.META.get("HTTP_X_GOOG_RESOURCE_STATE")
        if resource_state == "sync":
            return Response(status=status.HTTP_200_OK)

        channel_id = request.META.get("HTTP_X_GOOG_CHANNEL_ID")
        resource_id = request.META.get("HTTP_X_GOOG_RESOURCE_ID")
        token = request.META.get("HTTP_X_GOOG_CHANNEL_TOKEN")
        if not channel_id or not resource_id or not token:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Look up via GoogleCalendarSync and validate webhook token
        sync_state = (
            GoogleCalendarSync.objects
            .select_related("calendar__user")
            .filter(channel_id=channel_id, resource_id=resource_id, webhook_token=token)
            .first()
        )
        if not sync_state:
            return Response(status=status.HTTP_404_NOT_FOUND)

        cal = sync_state.calendar
        if sync_state.paused:
            # Initial sync is running — skip incremental to avoid race condition
            return Response(status=status.HTTP_200_OK)

        try:
            svc = GoogleCalendarService(cal.user)
            svc.sync_events(calendar=cal)
            sse.publish(
                cal.user_id,
                {
                    "type": "calendar_sync",
                    "calendar_id": cal.id,
                },
            )
        except Exception as exc:
            logger.exception("Failed processing Google webhook for calendar %s", cal.id, exc_info=exc)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(status=status.HTTP_200_OK)

    def get(self, request):
        # Google can ping with GET/HEAD during verification; respond OK.
        return Response(status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class EventStreamAPIView(APIView):
    # Use AllowAny so DRF never blocks with 403 — we check auth manually below
    # using the raw Django request, bypassing DRF's ASGI-unfriendly lazy auth.
    permission_classes = [AllowAny]
    authentication_classes = []
    renderer_classes = [SSERenderer]

    def get(self, request):
        # Read auth directly from Django's middleware-populated user, not DRF's
        # lazy wrapper — avoids sync/async context issues under Daphne/ASGI.
        django_user = request._request.user
        if not django_user.is_authenticated:
            # Yield a single close event so EventSource stops retrying immediately
            # instead of hammering the server with repeated 403s.
            def _unauth():
                yield "event: close\ndata: unauthorized\n\n"
            resp = StreamingHttpResponse(_unauth(), content_type="text/event-stream")
            resp["Cache-Control"] = "no-cache"
            return resp

        user_id = django_user.id
        # Last-Event-ID is sent automatically by the browser's EventSource on
        # reconnect.  If it's a numeric notification ID we query the DB for any
        # notifications the client missed and replay them before the live stream.
        last_event_id = request.META.get("HTTP_LAST_EVENT_ID", "").strip()
        q = sse.subscribe(user_id)

        def event_stream():
            try:
                # ── Replay phase ──────────────────────────────────────────
                if last_event_id and last_event_id.isdigit():
                    from chore_sync.models import Notification
                    missed = (
                        Notification.objects
                        .filter(
                            recipient_id=user_id,
                            id__gt=int(last_event_id),
                            dismissed=False,
                        )
                        .order_by("id")
                    )
                    for n in missed:
                        payload = json.dumps({
                            "type": "notification",
                            "id": str(n.id),
                            "notification_type": n.type,
                            "title": n.title,
                            "content": n.content,
                            "read": n.read,
                            "dismissed": n.dismissed,
                            "created_at": n.created_at.isoformat(),
                            "group_id": str(n.group_id) if n.group_id else None,
                            "task_occurrence_id": n.task_occurrence_id,
                            "task_swap_id": n.task_swap_id,
                            "task_proposal_id": n.task_proposal_id,
                            "action_url": n.action_url or "",
                        })
                        yield f"id: {n.id}\ndata: {payload}\n\n"

                # ── Live stream ───────────────────────────────────────────
                yield "event: ping\ndata: connected\n\n"
                while True:
                    try:
                        ev = q.get(timeout=3)
                        if ev is None:
                            continue
                        yield f"id: {ev.event_id}\ndata: {ev.payload}\n\n"
                    except queue.Empty:
                        yield "event: ping\ndata: keepalive\n\n"
                        continue
            finally:
                sse.unsubscribe(user_id, q)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


@method_decorator(csrf_exempt, name="dispatch")
class GoogleCalendarAuthURLAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def get(self, request):
        try:
            from django.core import signing
            svc = GoogleCalendarService(request.user)
            url, code_verifier = svc.build_auth_url()
            mobile = request.query_params.get("mobile") == "true"
            if mobile:
                # Embed verifier + user identity in a signed state so the callback
                # can authenticate without a session cookie (mobile browser redirect).
                state = signing.dumps(
                    {"uid": str(request.user.id), "cv": code_verifier or "", "mobile": True},
                    salt="google_oauth",
                    compress=True,
                )
                # Append state to the auth URL
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}state={state}"
            else:
                if code_verifier:
                    request.session["google_pkce_verifier"] = code_verifier
            return Response({"auth_url": url}, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@method_decorator(csrf_exempt, name="dispatch")
class GoogleCalendarCallbackAPIView(APIView):
    """GET /api/calendar/google/callback/

    AllowAny because Google redirects here from the browser — no session cookie or
    JWT is guaranteed.  User identity comes from either:
      • The signed `state` param (mobile flow, set by GoogleCalendarAuthURLAPIView)
      • The Django session (web flow — PKCE verifier stored in session)
    """
    permission_classes = [AllowAny]
    # Session auth must run so request.user is populated for the web flow.
    # AllowAny means unauthenticated mobile requests still proceed.
    authentication_classes = [CsrfExemptSessionAuthentication]

    def get(self, request):
        from django.core import signing
        from django.core.signing import BadSignature
        frontend_url = getattr(settings, "FRONTEND_APP_URL", "http://localhost:5173")
        mobile_redirect_uri = getattr(settings, "MOBILE_CALENDAR_REDIRECT_URI", "choresync://calendar/connected")

        code = request.query_params.get("code")
        if not code:
            return redirect(f"{frontend_url}/home?google_sync=error")

        state = request.query_params.get("state")
        is_mobile = False
        user = None
        code_verifier = None

        # Django-signed states always contain ":" — Google's own random state does not.
        # Only attempt to unsign if it looks like our signed payload.
        is_signed_state = state and ":" in state

        if is_signed_state:
            # Mobile flow: decode signed state
            try:
                data = signing.loads(state, salt="google_oauth", max_age=600)
                uid = data["uid"]
                code_verifier = data.get("cv") or None
                is_mobile = bool(data.get("mobile", False))
                User = get_user_model()
                user = User.objects.get(pk=uid)
            except (BadSignature, Exception) as exc:
                logger.warning("Google callback: invalid signed state — %s", exc)
                return redirect(f"{frontend_url}/home?google_sync=error")
        else:
            # Web flow: Google's own state param is ignored; user identity comes from session
            if not request.user or not request.user.is_authenticated:
                return redirect(f"{frontend_url}/home?google_sync=error")
            user = request.user
            code_verifier = request.session.pop("google_pkce_verifier", None)

        try:
            svc = GoogleCalendarService(user)
            svc.exchange_code(code, code_verifier=code_verifier)
            if is_mobile:
                return redirect(f"{mobile_redirect_uri}?provider=google")
            return redirect(f"{frontend_url}/home?google_sync=success")
        except Exception as exc:
            logger.exception("Google callback failed", exc_info=exc)
            if is_mobile:
                return redirect(f"{mobile_redirect_uri}?provider=google&error=1")
            return redirect(f"{frontend_url}/home?google_sync=error")


@method_decorator(csrf_exempt, name="dispatch")
class GoogleCalendarSyncAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def post(self, request, pk=None, *args, **kwargs):
        try:
            svc = GoogleCalendarService(request.user)
            count = svc.sync_events()
            return Response({"detail": f"Synced {count} events from Google."}, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": "Failed to sync Google events."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CalendarStatusAPIView(APIView):
    """GET /api/calendar/status/ — returns connection status for each provider.

    Response: { "google": { "connected": bool }, "outlook": { "connected": bool } }
    Checks ExternalCredential existence directly for provider keys actually used by
    persisted credentials: "google" for Google Calendar, "microsoft" for Outlook.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def get(self, request):
        from chore_sync.models import ExternalCredential
        # Only report calendar-connected when a credential with actual OAuth tokens exists
        # (expires_at is set). SSO-only credentials (secret={"sub":...}, no expires_at)
        # cannot be used to call the calendar APIs.
        google_connected = ExternalCredential.objects.filter(
            user=request.user, provider="google", expires_at__isnull=False,
        ).exists()
        outlook_connected = ExternalCredential.objects.filter(
            user=request.user, provider="microsoft", expires_at__isnull=False,
        ).exists()
        return Response({
            "google": {"connected": google_connected},
            "outlook": {"connected": outlook_connected},
        })


class UserCalendarListAPIView(APIView):
    """GET /api/calendars/ — list all Calendar rows belonging to the requesting user.

    Used by the frontend to populate the calendar picker in the create-event form,
    including calendars that have no events yet (e.g. freshly connected Google calendars).
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication, JWTAuthentication]

    def get(self, request):
        from chore_sync.models import Calendar
        cals = Calendar.objects.filter(user=request.user).order_by("provider", "name")
        return Response([
            {
                "id": c.id,
                "name": c.name,
                "provider": c.provider,
                "color": c.color or "",
                "push_enabled": c.push_enabled,
                "is_task_writeback": c.is_task_writeback,
                "include_in_availability": c.include_in_availability,
            }
            for c in cals
        ])
