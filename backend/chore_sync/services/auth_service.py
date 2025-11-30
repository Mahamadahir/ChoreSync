from __future__ import annotations


import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError, ObjectDoesNotExist
from django.core.mail import send_mail
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.db.models import Q

from email_validator import validate_email as comp_validate_email, EmailNotValidError

from ..domain_errors import (
    UsernameAlreadyTaken,
    EmailAlreadyTaken,
    InvalidEmail,
    WeakPassword,
    RegistrationError,
    VerificationTokenInvalid,
    VerificationTokenUsed,
    VerificationTokenExpired,
    InvalidCredentials,
    InactiveAccount,
)
from ..models import Calendar, EmailVerificationToken, PasswordResetToken, EmailLog
from ..dtos.user_dtos import UserDTO


User = get_user_model()
logger = logging.getLogger(__name__)


class AccountService:
    """All Account related services"""

    #helpers for register_user


    def _get_user(self, user_dto: UserDTO) -> User | None:
        try:
            return User.objects.get(username=user_dto.username)
        except ObjectDoesNotExist:
            return None

    def _normalize_email(self, email: str) -> str:
        """Normalize and syntax-validate an email (no uniqueness check)."""
        try:
            info = comp_validate_email(
                email.strip().lower(),
                check_deliverability=False,
            )
            return info.normalized
        except EmailNotValidError as exc:
            raise InvalidEmail(str(exc)) from exc

    def _validate_email_address(self, email: str) -> str:
        """Validate email for registration (enforces uniqueness)."""
        normalised_email = self._normalize_email(email)
        if User.objects.filter(email=normalised_email).exists():
            raise EmailAlreadyTaken(
                f"This email address ({normalised_email}) is already registered."
            )
        return normalised_email

    def _validate_username(self, username: str, *, exclude_user_id: int | None = None) -> str:
        """Normalize username and ensure uniqueness (optionally excluding one user)."""
        normalised_username = username.strip().lower()
        qs = User.objects.filter(username=normalised_username)
        if exclude_user_id is not None:
            qs = qs.exclude(pk=exclude_user_id)
        if qs.exists():
            raise UsernameAlreadyTaken(f"This username ({normalised_username}) is already in use.")
        return normalised_username

    def _validate_password_strength(self, password: str) -> None:
        """ Validate password with validators from settings
            Raises : WeakPassword
        """
        try:
            validate_password(password)
        except DjangoValidationError as exc:
            raise WeakPassword(exc.messages) from exc  #shows a list of readable error messages

    def _create_internal_calendar(self, user: User) -> Calendar:
        """Creates user's internal calendar - this is called within a transaction."""
        return Calendar.objects.create(
            user=user,
            provider="internal",
            name=f"{user.get_username()}'s calendar",
            color="grey",
            timezone=getattr(user, "timezone", "UTC"),
        )

    def register_user(self, *, username: str, email: str, password: str, timezone: str | None = None) -> UserDTO:
        """
        Orchestrates full registration:
        - validate username/email/password
        - create user
        - start email verification
        """
        # Normalise raw inputs
        raw_email = email.strip()
        raw_username = username.strip()

        # 1) Validate
        email_norm = self._validate_email_address(raw_email)
        username_norm = self._validate_username(raw_username)
        self._validate_password_strength(password)

        # 2) Create user in a transaction
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username_norm,
                    email=email_norm,
                    password=password,
                    is_active=False,         # activate only after email verification
                )
                if timezone:
                    setattr(user, "timezone", timezone.strip())
                    user.save(update_fields=["timezone"])
                self._create_internal_calendar(user)

        except IntegrityError as exc:
            # Edge case 2 separate users attempt to signup with the same username/email at the same time.
            msg = str(exc).lower()
            if "username" in msg:
                raise UsernameAlreadyTaken(f"Username '{username_norm}' is already in use.") from exc
            if "email" in msg:
                raise EmailAlreadyTaken(f"Email '{email_norm}' is already in use.") from exc
            raise RegistrationError("Could not create account due to a database error.") from exc

        # Note: verification email is triggered separately (e.g., after redirect to "check inbox" page)
        # to avoid blocking signup flow; account stays inactive until verified.

        # Return DTO
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            email_verified=getattr(user, "email_verified", False),
        )

    # ----- email verification -----

    def start_email_verification(self, user: User, token_obj: EmailVerificationToken | None = None) -> None:
        """
        Generate a token, store it, and send a confirmation link.
        """
        token_obj = token_obj or EmailVerificationToken.generate_for_user(user)

        # Build frontend URL like https://app.example.com/verify-email?token=...
        base_url = getattr(settings, "FRONTEND_VERIFY_EMAIL_URL", "http://localhost:5173/verify-email")
        verify_url = f"{base_url}?token={token_obj.token}"

        subject = "Confirm your email for ChoreSync"
        message = (
            "Hi,\n\n"
            "Please confirm your email address for your ChoreSync account by clicking the link below:\n\n"
            f"{verify_url}\n\n"
            "If you did not create this account, you can ignore this email.\n"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        EmailLog.objects.create(
            to_address=user.email,
            subject=subject,
            body=message,
            context={"type": "verify_email", "user_id": user.id},
        )

    def _enqueue_verification_email(self, user: User) -> None:
        """
        Hand off verification email work to a background queue.

        NOTE: Uses Celery task; if Celery is not running, falls back to sync send.
        """
        try:
            # Local import to avoid circular import at module load time
            from chore_sync.tasks import send_verification_email_task

            send_verification_email_task.delay(user.id)
        except Exception:
            # Fallback: synchronous send to avoid breaking the flow in dev
            self.start_email_verification(user)

    def send_verification_email_with_cooldown(self, email: str, *, min_interval_seconds: int = 60) -> None:
        """
        Trigger a verification email if allowed by cooldown.
        Raises RegistrationError for cooldown/ send failures; InvalidEmail if address invalid.
        """
        email_norm = self._normalize_email(email)
        try:
            user = User.objects.get(email=email_norm)
        except User.DoesNotExist:
            # Do not reveal account existence to caller.
            raise User.DoesNotExist

        last_token = (
            EmailVerificationToken.objects.filter(user=user)
            .order_by("-created_at")
            .first()
        )
        if last_token and (timezone.now() - last_token.created_at).total_seconds() < min_interval_seconds:
            raise RegistrationError("Please wait before requesting another verification email.")

        # Slow deliverability check before sending
        try:
            comp_validate_email(email_norm, check_deliverability=True)
        except EmailNotValidError as exc:
            raise InvalidEmail(str(exc)) from exc

        token_obj = EmailVerificationToken.generate_for_user(user)
        try:
            self._enqueue_verification_email(user)
        except Exception as exc:
            logger.exception("Failed to send verification email", exc_info=exc)
            raise RegistrationError("Unable to send verification email. Please check the address.") from exc

    def verify_email_token(self, token: str) -> UserDTO:
        """
        Given a token from a link, mark the user's email as verified.
        """
        with transaction.atomic():
            try:
                token_obj = EmailVerificationToken.objects.select_related("user").select_for_update().get(token=token)
            except EmailVerificationToken.DoesNotExist as exc:
                raise VerificationTokenInvalid("This verification link is invalid.") from exc

            if token_obj.used_at is not None:
                raise VerificationTokenUsed("This verification link has already been used.")

            if token_obj.is_expired():
                raise VerificationTokenExpired("This verification link has expired.")

            user = token_obj.user
            user.email_verified = True
            user.is_active = True
            user.save(update_fields=["email_verified", "is_active"])

            token_obj.mark_used()

        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            email_verified=user.email_verified,
        )

    def update_email_and_resend_verification(self, token: str, new_email: str) -> UserDTO:
        """
        Given a verification token and a new email, update the user's email if the token is valid,
        then send a new verification email.
        """
        with transaction.atomic():
            try:
                token_obj = (
                    EmailVerificationToken.objects.select_related("user")
                    .select_for_update()
                    .get(token=token)
                )
            except EmailVerificationToken.DoesNotExist as exc:
                raise VerificationTokenInvalid("This verification link is invalid.") from exc

            if token_obj.used_at is not None:
                raise VerificationTokenUsed("This verification link has already been used.")

            if token_obj.is_expired():
                raise VerificationTokenExpired("This verification link has expired.")

            # Validate new email uniqueness
            new_email_norm = self._validate_email_address(new_email)

            user = token_obj.user
            user.email = new_email_norm
            user.email_verified = False
            user.is_active = False
            user.save(update_fields=["email", "email_verified", "is_active"])

            # Invalidate old token and issue a new one
            token_obj.mark_used()
            new_token = EmailVerificationToken.generate_for_user(user)
            # Send immediately (sync) since Celery is deferred
            self.start_email_verification(user, token_obj=new_token)

        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            email_verified=user.email_verified,
        )

    def update_profile(self, user: User, *, username: str | None = None, email: str | None = None, timezone: str | None = None) -> UserDTO:
        """
        Update basic profile fields. Username uniqueness is enforced; email changes force re-verification.
        """
        dirty_fields: list[str] = []

        if username is not None and username.strip():
            username_norm = self._validate_username(username, exclude_user_id=user.pk)
            if username_norm != user.username:
                user.username = username_norm
                dirty_fields.append("username")

        if email is not None:
            new_email_norm = self._validate_email_address(email)
            if new_email_norm != user.email:
                user.email = new_email_norm
                user.email_verified = False
                user.is_active = False
                dirty_fields.extend(["email", "email_verified", "is_active"])
                token_obj = EmailVerificationToken.generate_for_user(user)
                self.start_email_verification(user, token_obj=token_obj)

        if timezone is not None and hasattr(user, "timezone"):
            setattr(user, "timezone", timezone)
            dirty_fields.append("timezone")

        if dirty_fields:
            user.save(update_fields=dirty_fields)

        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            email_verified=getattr(user, "email_verified", False),
        )

    def authenticate(self, *, identifier: str, password: str) -> tuple[User, UserDTO]:
        """Authenticate by username or email. Returns both the user model and DTO."""
        ident_norm = identifier.strip().lower()
        try:
            user = User.objects.get(Q(username__iexact=ident_norm) | Q(email__iexact=ident_norm))
        except User.DoesNotExist as exc:
            raise InvalidCredentials("Invalid username/email or password.") from exc

        if not user.check_password(password):
            raise InvalidCredentials("Invalid username/email or password.")

        if not user.is_active:
            raise InactiveAccount("Account is not active. Please verify your email.")

        dto = UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            email_verified=getattr(user, "email_verified", False),
        )
        return user, dto


    def send_password_reset(self, email: str) -> None:
        email_norm = self._normalize_email(email)
        try:
            user = User.objects.get(email=email_norm)
        except User.DoesNotExist:
            # Do not leak existence
            raise User.DoesNotExist
        if not user.is_active:
            raise InactiveAccount("Account is not active.")
        token_obj = PasswordResetToken.generate_for_user(user, lifetime_hours=1)
        reset_url = f"{getattr(settings, 'FRONTEND_RESET_PASSWORD_URL', 'http://localhost:5173/reset-password')}?token={token_obj.token}"
        subject = "Reset your password"
        message = (
            "We received a request to reset your password.\n\n"
            f"Reset link: {reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        EmailLog.objects.create(
            to_address=user.email,
            subject=subject,
            body=message,
            context={"type": "reset_password", "user_id": user.id},
        )

    def reset_password(self, token: str, new_password: str) -> UserDTO:
        with transaction.atomic():
            try:
                token_obj = (
                    PasswordResetToken.objects.select_related("user")
                    .select_for_update()
                    .get(token=token)
                )
            except PasswordResetToken.DoesNotExist as exc:
                raise VerificationTokenInvalid("This reset link is invalid.") from exc

            if token_obj.used_at is not None:
                raise VerificationTokenUsed("This reset link has already been used.")

            if token_obj.is_expired():
                raise VerificationTokenExpired("This reset link has expired.")

            user = token_obj.user
            self._validate_password_strength(new_password)
            user.set_password(new_password)
            user.save(update_fields=["password"])
            token_obj.mark_used()

        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            email_verified=getattr(user, "email_verified", False),
        )

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not user.check_password(current_password):
            raise InvalidCredentials("Current password is incorrect.")
        self._validate_password_strength(new_password)
        user.set_password(new_password)
        user.save(update_fields=["password"])



    def sign_in_with_google(self, *, id_token: str, nonce: str | None = None) -> None:
        """Sign a user in (or up) through Google identity tokens.

        Inputs:
            id_token: Google-provided JWT from the client.
            nonce: Optional nonce to prevent replay.
        Output:
            Session descriptor + profile or raises if token invalid/unlinked.
        TODO: Validate JWT signature/claims, enforce nonce, resolve linked ExternalCredential, create
        TODO: the account on first sign-in, and mint local session tokens + audit logs.
        """
        raise NotImplementedError("TODO: implement Google sign-in/up flow")

    def sign_in_with_microsoft(self, *, authorization_code: str, redirect_uri: str) -> None:
        """Sign a user in (or up) through the Microsoft identity platform.

        Inputs:
            authorization_code: OAuth code from Microsoft.
            redirect_uri: Redirect URI used during the authorization request.
        Output:
            Local session/profile data or raises on token exchange failure.
        TODO: Exchange the code for tokens, validate tenant/app scopes, pull profile details, upsert
        TODO: the linked user credential, and issue local authentication tokens + telemetry.
        """
        raise NotImplementedError("TODO: implement Microsoft sign-in/up flow")

    def sign_in_with_apple(self, *, identity_token: str, user_payload: dict | None = None) -> None:
        """Sign a user in (or up) through Apple Sign In.

        Inputs:
            identity_token: Apple-issued JWT containing subject + email.
            user_payload: Optional user info payload returned only on first authorization.
        Output:
            Authenticated session descriptor or raises on signature/consent errors.
        TODO: Verify Apple signature + nonce, extract stable user identifier, capture name/email on
        TODO: first pass, persist ExternalCredential link, and mint local tokens/audit logs.
        """
        raise NotImplementedError("TODO: implement Apple sign-in/up flow")
