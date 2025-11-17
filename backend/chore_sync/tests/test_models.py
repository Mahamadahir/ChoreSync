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
    test_time = timezone.now()
    """Fixture to create a group owned by the test user."""
    group = models.Group.objects.create(
        name="Test Group",
        group_code="TEST123",           # Required unique field
        owner=user,
        reassignment_rule = 'after_n_tasks',
        reassignment_value=6,
        last_reassigned_at = test_time
    # Set the user as group owner
    )
    return group , test_time

@pytest.fixture
def membership(db, user,group):
    """Fixture to create a membership owned by the test user."""
    group_instance, _ = group
    test_time = timezone.now()
    membership = models.GroupMembership.objects.create(
        user=user,
        group=group_instance,
        role='member'
    )
    return membership, test_time

@pytest.fixture
def task_template(db, user, group):
    """Fixture to create a task template owned by the test user."""
    group, test_time = group
    task_template = models.TaskTemplate.objects.create(
        next_due=test_time,
        active=True,
        name='single task template',
        details='This is a test',
        creator=user,
        group=group
    )
    return task_template, test_time
@pytest.fixture
def task_occurrence(db, user, task_template):
    """Fixture to create a task occurrence owned by the test user."""
    task_template, test_time = task_template
    task_occurrence = models.TaskOccurrence.objects.create(
        template=task_template,
        assigned_to=user,
        deadline=test_time,
    )

    return task_occurrence, test_time
@pytest.fixture
def calendar(user):
    return models.Calendar.objects.create(
        user = user,
        name = 'Test Calendar',
        description = 'This is a testing Calendar to ensure that Calender is stored correctly in DB',

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
def test_user_can_join_group(user, group, membership):
    membership, test_time = membership
    group, group_time = group

    # Assert that the group appears in the user’s joined groups
    assert group in user.groups_joined.all()

    # Assert that the user shows up in the group's members
    assert membership in group.members.all()

    # Validate role and joined_at fields
    assert membership.role == 'member'
    assert membership.joined_at >= test_time

@pytest.mark.django_db
def test_group_entity(user, group) -> None:


    group , tested_time = group

    tested_time = timezone.now()
    group.last_reassigned_at = tested_time
    assert group.name == 'Test Group'
    assert group.owner == user
    assert group.group_code == 'TEST123'
    assert group.reassignment_rule == 'after_n_tasks'
    assert group.reassignment_value == 6
    assert group.last_reassigned_at == tested_time

@pytest.mark.django_db
def test_task_entity_todo(user, group, task_occurrence, task_template) -> None:
    """models.Task should describe a scheduled chore."""

    task_occurrence, occurrence_time = task_occurrence
    group, _ = group
    task_template, template_time = task_template

    assert task_template.group == group
    assert task_template.recurring_choice == 'none'
    assert task_template.recur_value is None
    assert task_template.next_due == template_time
    assert task_template.name == 'single task template'
    assert task_template.details == 'This is a test'
    assert task_template.estimated_hours == 1.0
    assert task_template.created_at >= template_time
    assert task_template.updated_at >= template_time


    assert task_occurrence.template == task_template
    assert task_occurrence.assigned_to == user
    assert task_occurrence.template.active == True
    assert task_occurrence.deadline == occurrence_time

@pytest.mark.django_db
def test_calendar_entity(user, calendar) -> None:
    """models.Calendar should represent a syncable calendar."""
    test_user = user
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
