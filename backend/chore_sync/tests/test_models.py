"""Placeholder tests for chore_sync.domain.models entities."""
from __future__ import annotations

from datetime import timedelta
from tkinter.font import names

import pytest

from chore_sync import models
from django.utils import timezone


@pytest.fixture
def user(db):
    """Fixture to create a test user."""
    return models.User.objects.create_user(
        username='testuser',
        email='testuser@example.com',
        password='Testpass123!'
    )

@pytest.fixture
def group(db, user):
    """Fixture to create a group owned by the test user."""
    return models.Group.objects.create(
        name="Test Group",
        group_code="TEST123",           # Required unique field
        owner=user                      # Set the user as group owner
    )

@pytest.mark.django_db
def test_user_entity(user, group) -> None:
    """models.User should model platform members."""

    # check if user is created properly


    assert user.email == 'testuser@example.com'
    assert user.check_password('Testpass123!')
    assert user.username == 'testuser'
    assert user.is_active

@pytest.mark.django_db
def test_user_can_join_group(user, group):
    # Create a group membership manually due to `through` relation
    membership = models.GroupMembership.objects.create(
        user=user,
        group=group,
        role='member'
    )

    # Assert that the group appears in the user’s joined groups
    assert group in user.groups_joined.all()

    # Assert that the user shows up in the group's members
    assert user in group.members.all()

    # Validate role and joined_at fields
    assert membership.role == 'member'
    assert membership.joined_at <= timezone.now()

@pytest.mark.django_db
def test_group_entity_todo() -> None:
    """models.Group should capture household metadata."""
    user = models.User.objects.create_user(
        username='testing',
        email='mrmahamadahir@gmail.com',
        password='Test_password123'
    )
    group = models.Group.objects.create(name='Testing', owner = user, group_code = 'abc234')
    group.reassignment_rule = 'after_n_tasks'
    group.reassignment_value = 6
    tested_time = timezone.now()
    group.last_reassigned_at = tested_time
    assert group.name == 'Testing'
    assert group.owner == user
    assert group.group_code == 'abc234'
    assert group.reassignment_rule == 'after_n_tasks'
    assert group.reassignment_value == 6
    assert group.last_reassigned_at == tested_time

@pytest.mark.django_db
def test_task_entity_todo() -> None:
    now = timezone.now()
    past = now - timedelta(days=1)
    future = now + timedelta(days=1)

    """models.Task should describe a scheduled chore."""
    user = models.User.objects.create_user(
        username='testing',
        email='mrmahamadahir@gmail.com',
        password='Test_password123'
    )
    group = models.Group.objects.create(name='Testing', owner=user, group_code='abc234')
    task_template = models.TaskTemplate.objects.create(
        next_due = future,
        active = True,
        name = 'single task template',
        details = 'This is a test',
        creator = user,
        group = group
    )
    task_occurrence = models.TaskOccurrence.objects.create(
        template = task_template,
        assigned_to = user,
        deadline = past,
    )
    assert task_occurrence.template == task_template
    assert task_occurrence.assigned_to == user
    assert task_occurrence.template.next_due == future
    assert task_occurrence.template.active == True
    assert task_occurrence.deadline == past

@pytest.mark.django_db
def test_calendar_entity_todo() -> None:
    """models.Calendar should represent a syncable calendar."""
    test_user = models.User.objects.create_user(
        username='testing',
        email='mrmahamadahir@gmail.com',
        password='Test_password123'
    )
    calendar = models.Calendar.objects.create(
        user = test_user,
        name = 'Test Calendar',
        description = 'This is a testing Calendar to ensure that Calender is stored correctly in DB',

    )
    assert calendar.user == test_user
    assert calendar.name == 'Test Calendar'
    assert calendar.description =='This is a testing Calendar to ensure that Calender is stored correctly in DB'


def test_event_entity_todo() -> None:
    """models.Event should represent a calendar entry."""
    pytest.skip("TODO: add assertions for models.Event")


def test_recurring_occurrence_entity_todo() -> None:
    """models.RecurringTaskOccurrence should track generated runs."""
    pytest.skip("TODO: add assertions for models.RecurringTaskOccurrence")


def test_message_entity_todo() -> None:
    """models.Message should capture group chat messages."""
    pytest.skip("TODO: add assertions for models.Message")


def test_message_receipt_entity_todo() -> None:
    """models.MessageReceipt should track delivery/read state."""
    pytest.skip("TODO: add assertions for models.MessageReceipt")


def test_task_swap_entity_todo() -> None:
    """models.TaskSwap should describe swap negotiations."""
    pytest.skip("TODO: add assertions for models.TaskSwap")


def test_notification_entity_todo() -> None:
    """models.Notification should represent user alerts."""
    pytest.skip("TODO: add assertions for models.Notification")


def test_task_proposal_entity_todo() -> None:
    """models.TaskProposal should represent pending task ideas."""
    pytest.skip("TODO: add assertions for models.TaskProposal")


def test_task_preference_entity_todo() -> None:
    """models.TaskPreference should capture member sentiment."""
    pytest.skip("TODO: add assertions for models.TaskPreference")


def test_task_vote_entity_todo() -> None:
    """models.TaskVote should capture decision votes."""
    pytest.skip("TODO: add assertions for models.TaskVote")


def test_external_credential_entity_todo() -> None:
    """models.ExternalCredential should store provider tokens."""
    pytest.skip("TODO: add assertions for models.ExternalCredential")


def test_group_calendar_entity_todo() -> None:
    """models.GroupCalendar should aggregate group scheduling."""
    pytest.skip("TODO: add assertions for models.GroupCalendar")


def test_synced_event_entity_todo() -> None:
    """models.SyncedEvent should map in-app events to providers."""
    pytest.skip("TODO: add assertions for models.SyncedEvent")
