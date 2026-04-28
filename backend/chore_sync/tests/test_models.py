"""Tests for non-trivial model logic."""
from __future__ import annotations

import datetime
from datetime import timedelta

import pytest
from django.utils import timezone

from chore_sync import models

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return models.User.objects.create_user(
        username='testuser',
        email='testuser@example.com',
        password='Testpass123!',
    )


@pytest.fixture
def group(user):
    return models.Group.objects.create(
        name='Test Group',
        group_code='TEST123',
        owner=user,
    )


@pytest.fixture
def recurring_task_template(user, group):
    return models.TaskTemplate.objects.create(
        recurring_choice='every_n_days',
        recur_value=3,
        next_due=timezone.now(),
        active=True,
        name='recurring task template',
        creator=user,
        group=group,
    )


# -------------------------------------------------------------------
# TaskTemplate.get_next_due_date
# -------------------------------------------------------------------

def test_get_next_due_date_every_n_days(recurring_task_template):
    t = recurring_task_template
    assert t.get_next_due_date() == t.next_due + timedelta(days=t.recur_value)


def test_get_next_due_date_weekly(user, group):
    now = timezone.now()
    t = models.TaskTemplate.objects.create(
        recurring_choice='weekly', next_due=now, active=True,
        name='weekly t', creator=user, group=group,
    )
    assert t.get_next_due_date() == now + timedelta(weeks=1)


def test_get_next_due_date_monthly_clamps_short_month(user, group):
    # Jan 31 → Feb 28 (non-leap year)
    base = timezone.make_aware(datetime.datetime(2025, 1, 31, 10, 0))
    t = models.TaskTemplate.objects.create(
        recurring_choice='monthly', next_due=base, active=True,
        name='monthly t', creator=user, group=group,
    )
    result = t.get_next_due_date()
    assert result.year == 2025 and result.month == 2 and result.day == 28


def test_get_next_due_date_monthly_clamps_april(user, group):
    # Mar 31 → Apr 30
    base = timezone.make_aware(datetime.datetime(2025, 3, 31, 10, 0))
    t = models.TaskTemplate.objects.create(
        recurring_choice='monthly', next_due=base, active=True,
        name='monthly t2', creator=user, group=group,
    )
    result = t.get_next_due_date()
    assert result.month == 4 and result.day == 30


def test_get_next_due_date_monthly_year_rollover(user, group):
    # Dec 15 → Jan 15 next year
    base = timezone.make_aware(datetime.datetime(2025, 12, 15, 10, 0))
    t = models.TaskTemplate.objects.create(
        recurring_choice='monthly', next_due=base, active=True,
        name='monthly t3', creator=user, group=group,
    )
    result = t.get_next_due_date()
    assert result.year == 2026 and result.month == 1 and result.day == 15


def test_get_next_due_date_custom_finds_next_weekday(user, group):
    # Monday 2025-04-28; next 'wed' should be 2025-04-30
    base = timezone.make_aware(datetime.datetime(2025, 4, 28, 9, 0))
    t = models.TaskTemplate.objects.create(
        recurring_choice='custom', days_of_week=['wed'], next_due=base,
        active=True, name='custom t', creator=user, group=group,
    )
    result = t.get_next_due_date()
    assert result.weekday() == 2  # Wednesday
    assert result.date() == datetime.date(2025, 4, 30)


def test_get_next_due_date_custom_skips_from_date_itself(user, group):
    # from_date is already a Wednesday — should return the *next* Wednesday, not today
    base = timezone.make_aware(datetime.datetime(2025, 4, 30, 9, 0))  # Wednesday
    t = models.TaskTemplate.objects.create(
        recurring_choice='custom', days_of_week=['wed'], next_due=base,
        active=True, name='custom t2', creator=user, group=group,
    )
    result = t.get_next_due_date()
    assert result.date() == datetime.date(2025, 5, 7)


def test_get_next_due_date_none_returns_none(user, group):
    t = models.TaskTemplate.objects.create(
        recurring_choice='none', next_due=timezone.now(), active=True,
        name='one-off t', creator=user, group=group,
    )
    assert t.get_next_due_date() is None
