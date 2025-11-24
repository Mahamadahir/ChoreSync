"""Model tests for chore_sync.domain.models entities."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from chore_sync import models

# Mark all tests in this file as needing the database
pytestmark = pytest.mark.django_db


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture
def user():
    """Fixture to create a base test user."""
    return models.User.objects.create_user(
        username='testuser',
        email='testuser@example.com',
        password='Testpass123!',
    )


@pytest.fixture
def other_user(db):
    return models.User.objects.create_user(
        username='seconduser',
        email='second@example.com',
        password='Testpass123!',
    )


@pytest.fixture
def group(user):
    """Fixture to create a group owned by the test user."""
    return models.Group.objects.create(
        name="Test Group",
        group_code="TEST123",
        owner=user,
        reassignment_rule='after_n_tasks',
        reassignment_value=6,
        last_reassigned_at=timezone.now(),
    )


@pytest.fixture
def membership(user, group):
    """Fixture to create a membership owned by the test user."""
    return models.GroupMembership.objects.create(
        user=user,
        group=group,
        role='member',
    )


@pytest.fixture
def task_template(user, group):
    """Fixture to create a basic non-recurring task template."""
    now = timezone.now()
    return models.TaskTemplate.objects.create(
        recurring_choice='none',
        recur_value=None,
        next_due=now,
        active=True,
        name='single task template',
        details='This is a test',
        estimated_hours=1.0,
        creator=user,
        group=group,
    )


@pytest.fixture
def recurring_task_template(user, group):
    """Fixture to create a recurring task template (every_n_days)."""
    now = timezone.now()
    return models.TaskTemplate.objects.create(
        recurring_choice='every_n_days',
        recur_value=3,
        next_due=now,
        active=True,
        name='recurring task template',
        details='Recurring test',
        estimated_hours=1.0,
        creator=user,
        group=group,
    )


@pytest.fixture
def task_occurrence(user, task_template):
    """Fixture to create a task occurrence."""
    now = timezone.now()
    return models.TaskOccurrence.objects.create(
        template=task_template,
        assigned_to=user,
        deadline=now,
    )


@pytest.fixture
def external_credential(user):
    """Fixture to create an ExternalCredential."""
    return models.ExternalCredential.objects.create(
        user=user,
        provider='google',
        secret={'access_token': 'abc', 'refresh_token': 'def'},
        account_email='user@gmail.com',
        scopes='calendar.read calendar.write',
        expires_at=timezone.now() + timedelta(hours=1),
    )


@pytest.fixture
def internal_calendar(user):
    """Fixture for an internal (in-app) calendar."""
    return models.Calendar.objects.create(
        user=user,
        provider='internal',
        name='Internal Calendar',
        description='Internal test calendar',
        timezone='UTC',
    )


@pytest.fixture
def external_calendar(user, external_credential):
    """Fixture for an external (Google) calendar."""
    return models.Calendar.objects.create(
        user=user,
        provider='google',
        external_id='google-cal-1',
        name='Google Calendar',
        description='Google test calendar',
        credential=external_credential,
        timezone='Europe/London',
        sync_enabled=True,
    )


@pytest.fixture
def event(internal_calendar):
    """Fixture for a basic event."""
    start = timezone.now()
    end = start + timedelta(hours=1)
    return models.Event.objects.create(
        calendar=internal_calendar,
        source='manual',
        title='Test Event',
        description='Manual event',
        start=start,
        end=end,
        blocks_availability=True,
    )


@pytest.fixture
def message(user, group):
    """Fixture for a basic message."""
    return models.Message.objects.create(
        group=group,
        sender=user,
        content='Hello, world!',
    )


@pytest.fixture
def message_receipt(user, message):
    """Fixture for a basic message receipt."""
    return models.MessageReceipt.objects.create(
        message=message,
        user=user,
        seen_at=timezone.now(),
    )


@pytest.fixture
def task_swap(task_occurrence, user):
    """Fixture for an open-ended TaskSwap."""
    return models.TaskSwap.objects.create(
        task=task_occurrence,
        from_user=user,
        to_user=None,
        status='pending',
        reason='I am busy today',
    )


@pytest.fixture
def task_proposal(user, group, task_template):
    """Fixture for a pending TaskProposal."""
    return models.TaskProposal.objects.create(
        proposed_by=user,
        group=group,
        task_template=task_template,
        reason='We should formalise this task.',
        state='pending',
        required_support_ratio=0.5,
    )


@pytest.fixture
def task_vote(user, task_proposal):
    """Fixture for a TaskVote."""
    return models.TaskVote.objects.create(
        proposal=task_proposal,
        voter=user,
        choice='support',
        note='Looks good.',
    )


@pytest.fixture
def task_preference(user, task_template):
    """Fixture for a TaskPreference."""
    return models.TaskPreference.objects.create(
        user=user,
        task_template=task_template,
        preference='prefer',
        reason='I like doing this.',
    )


@pytest.fixture
def notification(user, group, task_occurrence):
    """Fixture for a Notification."""
    return models.Notification.objects.create(
        recipient=user,
        type='task_assigned',
        group=group,
        task_occurrence=task_occurrence,
        content='You have been assigned a task.',
    )


@pytest.fixture
def group_calendar(group):
    """Fixture for GroupCalendar settings."""
    return models.GroupCalendar.objects.create(
        group=group,
        timezone='UTC',
        show_member_calendars=True,
        show_group_tasks=True,
    )


# -------------------------------------------------------------------
# User / Group / Membership
# -------------------------------------------------------------------

def test_user_entity(user):
    """models.User should model platform members correctly."""
    assert user.email == 'testuser@example.com'
    assert user.username == 'testuser'
    assert user.is_active
    assert user.check_password('Testpass123!')
    assert user.on_time_streak_days == 0
    assert user.longest_on_time_streak_days == 0
    assert user.last_streak_date is None
    assert str(user) == user.email


def test_user_can_join_group(user, group, membership):
    """User <-> GroupMembership relationships should be wired correctly."""
    # user sees group via many-to-many
    assert group in user.groups_joined.all()
    # group sees membership
    assert membership in group.members.all()
    # membership fields
    assert membership.role == 'member'
    assert membership.joined_at is not None


def test_group_entity(user, group):
    """models.Group should hold configuration and owner."""
    assert group.name == 'Test Group'
    assert group.group_code == 'TEST123'
    assert group.owner == user
    assert group.reassignment_rule == 'after_n_tasks'
    assert group.reassignment_value == 6
    assert group.last_reassigned_at is not None
    assert str(group) == group.group_code


def test_group_owner_set_null_on_user_delete(group, user):
    """Deleting the owner should SET_NULL on Group.owner."""
    group_id = group.id
    user.delete()
    group_refetched = models.Group.objects.get(id=group_id)
    assert group_refetched.owner is None


# -------------------------------------------------------------------
# TaskTemplate / TaskOccurrence
# -------------------------------------------------------------------

def test_task_template_defaults(task_template, group, user):
    """TaskTemplate should be linked to group and creator with sensible defaults."""
    t = task_template
    assert t.group == group
    assert t.creator == user
    assert t.recurring_choice == 'none'
    assert t.recur_value is None
    assert t.importance == 'core'
    assert t.active is True
    assert t.estimated_hours == 1.0
    assert t.created_at is not None
    assert t.updated_at is not None
    assert str(t) == f"{t.name} ({group.name})"


def test_task_template_clean_validation_invalid_recur_value(group, user):
    """TaskTemplate.clean should enforce consistency of recurrence fields."""
    now = timezone.now()
    # invalid: recurring_choice='none' but recur_value is set
    bad = models.TaskTemplate(
        recurring_choice='none',
        recur_value=3,
        next_due=now,
        active=True,
        name='Bad template',
        details='invalid',
        creator=user,
        group=group,
    )
    with pytest.raises(Exception):
        bad.full_clean()

    # invalid: recurring_choice!='none' but recur_value is None
    bad2 = models.TaskTemplate(
        recurring_choice='every_n_days',
        recur_value=None,
        next_due=now,
        active=True,
        name='Bad template 2',
        details='invalid',
        creator=user,
        group=group,
    )
    with pytest.raises(Exception):
        bad2.full_clean()


def test_task_template_get_next_due_date(recurring_task_template):
    """get_next_due_date should advance by recur_value days for every_n_days."""
    t = recurring_task_template
    base = t.next_due
    next_due = t.get_next_due_date()
    assert next_due == base + timedelta(days=t.recur_value)


def test_task_occurrence_entity(task_occurrence, task_template, user):
    """TaskOccurrence should link template, assignee, and deadline."""
    occ = task_occurrence
    assert occ.template == task_template
    assert occ.assigned_to == user
    assert occ.deadline is not None
    assert occ.completed is False
    assert occ.completed_at is None
    assert str(occ).startswith(task_template.name)


def test_task_occurrence_cascade_on_template_delete(task_occurrence, task_template):
    """Deleting a TaskTemplate should cascade delete TaskOccurrences."""
    assert models.TaskOccurrence.objects.filter(id=task_occurrence.id).exists()
    task_template.delete()
    assert not models.TaskOccurrence.objects.filter(id=task_occurrence.id).exists()


def test_task_occurrence_assigned_to_set_null_on_user_delete(task_occurrence, user):
    """Deleting an assigned user should SET_NULL on TaskOccurrence.assigned_to."""
    occ_id = task_occurrence.id
    user.delete()
    occ = models.TaskOccurrence.objects.get(id=occ_id)
    assert occ.assigned_to is None


# -------------------------------------------------------------------
# ExternalCredential / Calendar / Event
# -------------------------------------------------------------------

def test_external_credential_entity(external_credential, user):
    """ExternalCredential should store provider tokens."""
    cred = external_credential
    assert cred.user == user
    assert cred.provider == 'google'
    assert 'access_token' in cred.secret
    assert cred.account_email == 'user@gmail.com'
    assert cred.is_expired() is False
    assert str(cred).startswith(user.email)


def test_calendar_entity(internal_calendar, user):
    """Calendar should represent a syncable calendar source."""
    cal = internal_calendar
    assert cal.user == user
    assert cal.provider == 'internal'
    assert cal.name == 'Internal Calendar'
    assert cal.description == 'Internal test calendar'
    assert cal.include_in_availability is True
    assert str(cal).startswith(user.email)


def test_calendar_deleted_with_user(internal_calendar, user):
    """Deleting a user should cascade delete their calendars."""
    cal_id = internal_calendar.id
    user.delete()
    assert not models.Calendar.objects.filter(id=cal_id).exists()


def test_calendar_credential_set_null_on_credential_delete(external_calendar, external_credential):
    """Deleting an ExternalCredential should SET_NULL on Calendar.credential."""
    cal_id = external_calendar.id
    external_credential.delete()
    cal = models.Calendar.objects.get(id=cal_id)
    assert cal.credential is None


def test_event_entity(event, internal_calendar):
    """Event should represent a calendar entry."""
    e = event
    assert e.calendar == internal_calendar
    assert e.source == 'manual'
    assert e.title == 'Test Event'
    assert e.start < e.end
    assert e.blocks_availability is True
    assert str(e) == e.title


def test_event_deleted_with_calendar(event, internal_calendar):
    """Deleting a calendar should delete its events."""
    event_id = event.id
    internal_calendar.delete()
    assert not models.Event.objects.filter(id=event_id).exists()


def test_event_task_occurrence_set_null_on_task_delete(task_occurrence, internal_calendar):
    """Deleting a TaskOccurrence should SET_NULL on Event.task_occurrence."""
    # create an event linked to a task_occurrence
    start = timezone.now()
    end = start + timedelta(hours=1)
    e = models.Event.objects.create(
        calendar=internal_calendar,
        source='task',
        title='Task Event',
        start=start,
        end=end,
        task_occurrence=task_occurrence,
    )
    event_id = e.id
    task_occurrence.delete()
    e_refetched = models.Event.objects.get(id=event_id)
    assert e_refetched.task_occurrence is None


# -------------------------------------------------------------------
# Messaging and receipts
# -------------------------------------------------------------------

def test_message_entity(message, user, group):
    """Message should capture group chat messages."""
    m = message
    assert m.group == group
    assert m.sender == user
    assert m.content == 'Hello, world!'
    assert m.timestamp is not None
    assert 'Hello' in str(m)


def test_message_deleted_with_group(message, group):
    """Deleting a group should delete its messages."""
    msg_id = message.id
    group.delete()
    assert not models.Message.objects.filter(id=msg_id).exists()


def test_message_sender_set_null_on_user_delete(message, user):
    """Deleting the sender should SET_NULL on Message.sender."""
    msg_id = message.id
    user.delete()
    m = models.Message.objects.get(id=msg_id)
    assert m.sender is None


def test_message_receipt_entity(message_receipt, message, user):
    """MessageReceipt should track per-user read status."""
    r = message_receipt
    assert r.message == message
    assert r.user == user
    assert r.seen_at is not None


def test_message_receipt_deleted_with_message(message_receipt, message):
    """Deleting a message should delete its receipts."""
    receipt_id = message_receipt.id
    message.delete()
    assert not models.MessageReceipt.objects.filter(id=receipt_id).exists()


def test_message_receipt_deleted_with_user(message_receipt, user):
    """Deleting a user should delete their message receipts."""
    receipt_id = message_receipt.id
    user.delete()
    assert not models.MessageReceipt.objects.filter(id=receipt_id).exists()


# -------------------------------------------------------------------
# TaskSwap
# -------------------------------------------------------------------

def test_task_swap_entity(task_swap, task_occurrence, user):
    """TaskSwap should describe swap negotiations."""
    s = task_swap
    assert s.task == task_occurrence
    assert s.from_user == user
    assert s.to_user is None  # open-ended by default
    assert s.status == 'pending'
    assert s.created_at is not None
    assert 'Swap for' in str(s)


def test_task_swap_deleted_with_task(task_swap, task_occurrence):
    """Deleting TaskOccurrence should delete related TaskSwap."""
    swap_id = task_swap.id
    task_occurrence.delete()
    assert not models.TaskSwap.objects.filter(id=swap_id).exists()


def test_task_swap_users_set_null_on_user_delete(task_swap, user, other_user, task_occurrence):
    """Deleting from_user/to_user should SET_NULL, keeping the swap row."""
    # Attach a to_user first
    task_swap.to_user = other_user
    task_swap.save()

    swap_id = task_swap.id

    # Delete from_user
    user.delete()
    s = models.TaskSwap.objects.get(id=swap_id)
    assert s.from_user is None
    assert s.to_user == other_user

    # Delete to_user
    other_user.delete()
    s = models.TaskSwap.objects.get(id=swap_id)
    assert s.to_user is None


# -------------------------------------------------------------------
# TaskProposal / TaskVote
# -------------------------------------------------------------------

def test_task_proposal_entity(task_proposal, user, group, task_template):
    """TaskProposal should represent pending task ideas."""
    p = task_proposal
    assert p.proposed_by == user
    assert p.group == group
    assert p.task_template == task_template
    assert p.state == 'pending'
    assert p.required_support_ratio == 0.5
    assert p.is_open is True
    assert "Proposal for" in str(p)


def test_task_proposal_deleted_with_group(task_proposal, group):
    """Deleting group should delete its proposals."""
    proposal_id = task_proposal.id
    group.delete()
    assert not models.TaskProposal.objects.filter(id=proposal_id).exists()


def test_task_proposal_deleted_with_task_template(task_proposal, task_template):
    """Deleting the TaskTemplate should keep proposals but null the FK."""
    proposal_id = task_proposal.id
    task_template.delete()
    proposal = models.TaskProposal.objects.get(id=proposal_id)
    assert proposal.task_template is None


def test_task_proposal_proposed_by_set_null_on_user_delete(task_proposal, user):
    """Deleting proposer should SET_NULL on TaskProposal.proposed_by."""
    proposal_id = task_proposal.id
    user.delete()
    p = models.TaskProposal.objects.get(id=proposal_id)
    assert p.proposed_by is None


def test_task_vote_entity(task_vote, task_proposal, user):
    """TaskVote should capture decision votes."""
    v = task_vote
    assert v.proposal == task_proposal
    assert v.voter == user
    assert v.choice == 'support'
    assert 'voted' in str(v)


def test_task_vote_unique_per_user_and_proposal(task_proposal, user):
    """TaskVote should enforce one vote per user per proposal."""
    models.TaskVote.objects.create(
        proposal=task_proposal,
        voter=user,
        choice='support',
    )
    with pytest.raises(IntegrityError):
        models.TaskVote.objects.create(
            proposal=task_proposal,
            voter=user,
            choice='reject',
        )


def test_task_vote_deleted_with_proposal(task_vote, task_proposal):
    """Deleting a proposal should delete its votes."""
    vote_id = task_vote.id
    task_proposal.delete()
    assert not models.TaskVote.objects.filter(id=vote_id).exists()


def test_task_vote_deleted_with_voter(task_vote, user):
    """Deleting a voter should delete their votes."""
    vote_id = task_vote.id
    user.delete()
    assert not models.TaskVote.objects.filter(id=vote_id).exists()


# -------------------------------------------------------------------
# TaskPreference
# -------------------------------------------------------------------

def test_task_preference_entity(task_preference, user, task_template):
    """TaskPreference should capture member sentiment."""
    pref = task_preference
    assert pref.user == user
    assert pref.task_template == task_template
    assert pref.preference == 'prefer'
    assert pref.weight() == 1
    assert pref.last_updated is not None
    assert str(pref).startswith(str(user))


def test_task_preference_unique_per_user_and_template(user, task_template):
    """TaskPreference should only allow one row per (user, task_template)."""
    models.TaskPreference.objects.create(
        user=user,
        task_template=task_template,
        preference='avoid',
    )
    with pytest.raises(IntegrityError):
        models.TaskPreference.objects.create(
            user=user,
            task_template=task_template,
            preference='prefer',
        )


def test_task_preference_deleted_with_user(task_preference, user):
    """Deleting a user should delete their task preferences."""
    pref_id = task_preference.id
    user.delete()
    assert not models.TaskPreference.objects.filter(id=pref_id).exists()


def test_task_preference_deleted_with_template(task_preference, task_template):
    """Deleting a task template should delete preferences for it."""
    pref_id = task_preference.id
    task_template.delete()
    assert not models.TaskPreference.objects.filter(id=pref_id).exists()


# -------------------------------------------------------------------
# Notification
# -------------------------------------------------------------------

def test_notification_entity(notification, user, group, task_occurrence):
    """Notification should represent user alerts with optional targets."""
    n = notification
    assert n.recipient == user
    assert n.type == 'task_assigned'
    assert n.group == group
    assert n.task_occurrence == task_occurrence
    assert n.read is False
    assert n.dismissed is False
    assert n.created_at is not None
    assert "Notification to" in str(n)


def test_notification_deleted_with_recipient(notification, user):
    """Deleting a user should delete notifications sent to them."""
    n_id = notification.id
    user.delete()
    assert not models.Notification.objects.filter(id=n_id).exists()


def test_notification_deleted_with_group(notification, group):
    """Deleting a group should delete notifications pointing to it."""
    n_id = notification.id
    group.delete()
    assert not models.Notification.objects.filter(id=n_id).exists()


def test_notification_deleted_with_task_occurrence(notification, task_occurrence):
    """Deleting a task occurrence should delete notifications pointing to it."""
    n_id = notification.id
    task_occurrence.delete()
    assert not models.Notification.objects.filter(id=n_id).exists()


# -------------------------------------------------------------------
# GroupCalendar
# -------------------------------------------------------------------

def test_group_calendar_entity(group_calendar, group):
    """GroupCalendar should aggregate group scheduling settings."""
    gc = group_calendar
    assert gc.group == group
    assert gc.timezone == 'UTC'
    assert gc.show_member_calendars is True
    assert gc.show_group_tasks is True
    assert gc.created_at is not None
    assert "Group calendar settings" in str(gc)


def test_group_calendar_deleted_with_group(group_calendar, group):
    """Deleting a group should delete its GroupCalendar settings."""
    gc_id = group_calendar.id
    group.delete()
    assert not models.GroupCalendar.objects.filter(id=gc_id).exists()
