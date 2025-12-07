from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
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
)
from chore_sync.services.auth_service import AccountService
from chore_sync.services.google_calendar_service import GoogleCalendarService
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

User = get_user_model()
logger = logging.getLogger(__name__)


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session auth without CSRF enforcement (for API endpoints already gated by other means)."""

    def enforce_csrf(self, request):
        return  # skip CSRF checks for these API endpoints


def user_dto_to_dict(dto: UserDTO) -> dict:
    return {
        "id": dto.id,
        "username": dto.username,
        "email": dto.email,
        "is_active": dto.is_active,
        "email_verified": getattr(dto, "email_verified", False),
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
                # Return only minimal status flags; avoid exposing full user details
                "email_verified": getattr(user_dto, "email_verified", False),
                "detail": "Login successful.",
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class LogoutAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

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
    authentication_classes = [CsrfExemptSessionAuthentication]

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
            )
        except (InvalidEmail, EmailAlreadyTaken, RegistrationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Profile updated.",
                **user_dto_to_dict(user_dto),
                "username": user_dto.username,
                "timezone": getattr(request.user, "timezone", ""),
            },
            status=status.HTTP_200_OK,
        )


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
    authentication_classes = [CsrfExemptSessionAuthentication]

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
            },
            status=status.HTTP_200_OK,
        )


class EventsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication]

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
        if calendar.provider == "google":
            try:
                GoogleCalendarService(request.user).push_created_event(ev)
            except Exception as exc:
                logger.exception("Failed to push new event to Google", exc_info=exc)
                return Response(
                    {**out, "detail": "Event saved locally but failed to push to Google."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
        return Response(out, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class EventDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication]

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
        if ev.calendar.provider == "google":
            try:
                GoogleCalendarService(request.user).push_updated_event(ev)
            except Exception as exc:
                from chore_sync.services.google_calendar_service import GoogleEventConflict
                if isinstance(exc, GoogleEventConflict):
                    logger.warning("Conflict pushing event %s to Google", ev.id)
                    return Response(
                        {**out, "detail": "This event changed in Google. Please refresh and retry."},
                        status=status.HTTP_409_CONFLICT,
                    )
                logger.exception("Failed to push updated event to Google", exc_info=exc)
                return Response(
                    {**out, "detail": "Event updated locally but failed to push to Google."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
        return Response(out, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class GoogleCalendarAuthURLAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication]

    def get(self, request):
        try:
            svc = GoogleCalendarService(request.user)
            url = svc.build_auth_url()
            return Response({"auth_url": url}, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@method_decorator(csrf_exempt, name="dispatch")
class GoogleCalendarCallbackAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication]

    def get(self, request):
        code = request.query_params.get("code")
        if not code:
            return Response({"detail": "Missing code"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            svc = GoogleCalendarService(request.user)
            svc.exchange_code(code)
            count = svc.sync_events()
            frontend_url = getattr(settings, "FRONTEND_APP_URL", "http://localhost:5173")
            target = f"{frontend_url}?google_sync=success&imported={count}"
            return redirect(target)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Google callback failed", exc_info=exc)
            frontend_url = getattr(settings, "FRONTEND_APP_URL", "http://localhost:5173")
            target = f"{frontend_url}?google_sync=error"
            try:
                return redirect(target)
            except Exception:
                return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name="dispatch")
class GoogleCalendarSyncAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CsrfExemptSessionAuthentication]

    def post(self, request, pk=None, *args, **kwargs):
        try:
            svc = GoogleCalendarService(request.user)
            count = svc.sync_events()
            return Response({"detail": f"Synced {count} events from Google."}, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": "Failed to sync Google events."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
