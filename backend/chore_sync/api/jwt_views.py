"""JWT authentication views for the React Native mobile client."""
from __future__ import annotations

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as _BaseTokenRefreshView, TokenVerifyView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from django.conf import settings

from chore_sync.services.auth_service import (
    AccountService,
    InvalidCredentials,
    InactiveAccount,
    RegistrationError,
)


# ------------------------------------------------------------------ #
#  Custom serializer — tells simplejwt which fields to put in the token
# ------------------------------------------------------------------ #

class ChoresSyncTokenObtainSerializer(TokenObtainPairSerializer):
    """Adds email and username as extra claims in the JWT payload."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['username'] = user.username
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        return token


# ------------------------------------------------------------------ #
#  POST /api/auth/token/
#  Accepts { identifier, password } — mirrors the existing session login.
#  Returns { access, refresh, email_verified }
# ------------------------------------------------------------------ #

@method_decorator(csrf_exempt, name='dispatch')
class JWTObtainTokenAPIView(APIView):
    """Issue a JWT access + refresh token pair.

    Accepts the same ``identifier`` field (email or username) as the
    session-based login so the mobile app uses identical credentials.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        identifier = request.data.get('identifier', '').strip()
        password = request.data.get('password', '')

        if not identifier or not password:
            return Response(
                {'detail': 'identifier and password are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from chore_sync.models import AuthEvent
        try:
            user, user_dto = AccountService().authenticate(
                identifier=identifier,
                password=password,
            )
        except InvalidCredentials as exc:
            AuthEvent.log_from_request('login_failed', request, email=identifier, client='mobile')
            return Response({'detail': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        except InactiveAccount as exc:
            AuthEvent.log_from_request('login_failed', request, email=identifier, client='mobile', reason='inactive')
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)

        AuthEvent.log_from_request('login_success', request, user=user, client='mobile')
        refresh = RefreshToken.for_user(user)
        # Stamp extra claims
        refresh['email'] = user.email
        refresh['username'] = user.username
        refresh['first_name'] = user.first_name
        refresh['last_name'] = user.last_name

        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'email_verified': getattr(user_dto, 'email_verified', False),
            },
            status=status.HTTP_200_OK,
        )


def _jwt_response(user) -> dict:
    """Build the standard { access, refresh, email_verified } payload."""
    refresh = RefreshToken.for_user(user)
    refresh['email'] = user.email
    refresh['username'] = user.username
    refresh['first_name'] = user.first_name
    refresh['last_name'] = user.last_name
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'email_verified': getattr(user, 'email_verified', False),
    }


# ------------------------------------------------------------------ #
#  POST /api/auth/google/mobile/
#  Accepts { id_token: "..." } — Google ID token from expo-auth-session
#  Returns { access, refresh, email_verified }
# ------------------------------------------------------------------ #

@method_decorator(csrf_exempt, name='dispatch')
class GoogleMobileLoginAPIView(APIView):
    """Exchange a Google ID token (from Expo OAuth flow) for a JWT pair."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        id_token_str = request.data.get('id_token', '').strip()
        if not id_token_str:
            return Response({'detail': 'id_token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        mobile_client_ids = getattr(settings, 'GOOGLE_MOBILE_CLIENT_IDS', [])
        from chore_sync.models import AuthEvent
        try:
            user, _ = AccountService().sign_in_with_google(
                id_token=id_token_str,
                extra_audiences=mobile_client_ids,
            )
        except (InvalidCredentials, RegistrationError) as exc:
            AuthEvent.log_from_request('login_failed', request, provider='google', client='mobile', reason=str(exc))
            return Response({'detail': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        except InactiveAccount as exc:
            AuthEvent.log_from_request('login_failed', request, provider='google', client='mobile', reason='inactive')
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            AuthEvent.log_from_request('login_failed', request, provider='google', client='mobile', reason=str(exc))
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        AuthEvent.log_from_request('google_sso_login', request, user=user, client='mobile')
        return Response(_jwt_response(user), status=status.HTTP_200_OK)


# ------------------------------------------------------------------ #
#  POST /api/auth/microsoft/mobile/
#  Accepts { id_token: "..." } — Microsoft ID token from expo-auth-session
#  Returns { access, refresh, email_verified }
# ------------------------------------------------------------------ #

@method_decorator(csrf_exempt, name='dispatch')
class MicrosoftMobileLoginAPIView(APIView):
    """Exchange a Microsoft ID token (from Expo OAuth flow) for a JWT pair."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        id_token_str = request.data.get('id_token', '').strip()
        if not id_token_str:
            return Response({'detail': 'id_token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        from chore_sync.models import AuthEvent
        try:
            user, _ = AccountService().sign_in_with_microsoft(id_token=id_token_str)
        except (InvalidCredentials, RegistrationError) as exc:
            AuthEvent.log_from_request('login_failed', request, provider='microsoft', client='mobile', reason=str(exc))
            return Response({'detail': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        except InactiveAccount as exc:
            AuthEvent.log_from_request('login_failed', request, provider='microsoft', client='mobile', reason='inactive')
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            AuthEvent.log_from_request('login_failed', request, provider='microsoft', client='mobile', reason=str(exc))
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        AuthEvent.log_from_request('microsoft_sso_login', request, user=user, client='mobile')
        return Response(_jwt_response(user), status=status.HTTP_200_OK)


class TokenRefreshView(_BaseTokenRefreshView):
    """Wraps SimpleJWT's TokenRefreshView to write an audit entry on each refresh."""

    def post(self, request, *args, **kwargs):
        from chore_sync.models import AuthEvent
        from rest_framework_simplejwt.tokens import UntypedToken
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            try:
                # Decode the new access token to get the user id
                access = response.data.get('access', '')
                token = UntypedToken(access)
                user_id = token.get('user_id')
                from django.contrib.auth import get_user_model
                user = get_user_model().objects.filter(pk=user_id).first()
                AuthEvent.log_from_request('token_refreshed', request, user=user, client='mobile')
            except Exception:
                pass
        return response


# Re-export standard views so urls.py only imports from here
__all__ = [
    'JWTObtainTokenAPIView',
    'GoogleMobileLoginAPIView',
    'MicrosoftMobileLoginAPIView',
    'TokenRefreshView',
    'TokenVerifyView',
    'ChoresSyncTokenObtainSerializer',
]
