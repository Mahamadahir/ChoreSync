from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model

User = get_user_model()


@shared_task
def send_verification_email_task(user_id: int) -> None:
    # Import inside task to avoid circular import at module load
    from chore_sync.services.auth_service import AccountService

    svc = AccountService()
    user = User.objects.filter(id=user_id).first()
    if not user:
        return
    svc.start_email_verification(user)
