from __future__ import annotations

from rest_framework import serializers


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=1, max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=100)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(min_length=1)  # email or username
    password = serializers.CharField(min_length=1, write_only=True)


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=1)


class UpdateEmailSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=1)
    email = serializers.EmailField()


class ProfileSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False)
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=100)


class ForgotPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=1)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match.")
        return data


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match.")
        return data


class GoogleLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(min_length=10, write_only=True)


class MicrosoftLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField(min_length=10, write_only=True)


class EventSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    is_all_day = serializers.BooleanField()
    blocks_availability = serializers.BooleanField()
    source = serializers.CharField()
    calendar_id = serializers.IntegerField()
    calendar_name = serializers.CharField()
    calendar_color = serializers.CharField(allow_null=True, required=False)


class EventCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    is_all_day = serializers.BooleanField(default=False)
    blocks_availability = serializers.BooleanField(default=True)
    calendar_id = serializers.IntegerField(required=False)


class GoogleCalendarSelectionSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)
    color = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    include_in_availability = serializers.BooleanField()
    writable = serializers.BooleanField()
    timezone = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
