from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

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
)
from chore_sync.services.auth_service import AccountService
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

User = get_user_model()


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
                "is_active": user_dto.is_active,
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
        current_password = serializer.validated_data["current_password"]
        new_password = serializer.validated_data["new_password"]
        svc = AccountService()
        try:
            svc.change_password(request.user, current_password, new_password)
        except InvalidCredentials as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except WeakPassword as exc:
            return Response({"detail": exc.messages if hasattr(exc, 'messages') else str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)
