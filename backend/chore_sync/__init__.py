
from __future__ import annotations

# Ensure Celery app loads with Django
from .celery import app as celery_app  # noqa: F401

__all__ = ("celery_app",)
