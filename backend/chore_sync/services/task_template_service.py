"""Task template orchestration for reusable chore blueprints."""
from __future__ import annotations

from dataclasses import dataclass
from django.db import transaction
from chore_sync.models import Group, TaskTemplate, TaskOccurrence, GroupMembership
from django.contrib.auth import get_user_model

User = get_user_model()

@dataclass
class TaskTemplateService:
    """Manages reusable task templates for rapid household setup."""

    def create_template(self, *, creator: User, group_id: str, payload: dict) -> TaskTemplate:
        """Create and persist a new task template for a group.

        Inputs:
            creator: User creating the template (must be a group member).
            group_id: ID of the group the template belongs to.
            payload: Template fields (name, next_due, recurrence, difficulty, etc.).
                     created_at/updated_at are stripped if present; all other fields
                     are passed directly to the model — nullable/default fields are optional.
        Output:
            Saved TaskTemplate instance. Raises ValueError if group not found or creator
            is not a member. Raises ValidationError if model validation fails.
        """
        group = Group.objects.filter(id=group_id).first()
        if group is None:
            raise ValueError("Group not found.")
        membership = group.members.filter(user=creator).first()
        if membership is None:
            raise ValueError("Creator is not a member of this group.")
        if group.task_proposal_voting_required and membership.role != 'moderator':
            raise PermissionError(
                "Only moderators can create tasks directly in this group. "
                "Submit a suggestion instead."
            )

        payload.pop('created_at', None)
        payload.pop('updated_at', None)

        template = TaskTemplate(**payload, creator=creator, group_id=group_id)
        template.full_clean()
        template.save()
        return template


    def list_templates(self, *, group_id: str) -> list[TaskTemplate]:
        """Return all active templates for a group.

        Inputs:
            group_id: Group whose templates to return.
        Output:
            QuerySet of active TaskTemplate instances.
        """
        return list(TaskTemplate.objects.filter(group_id=group_id, active=True).order_by('name'))

    def update_template(self, *, template_id: str, actor_id: str, updates: dict) -> TaskTemplate:
        """Apply edits to an existing template.

        Inputs:
            template_id: Target template UUID.
            actor_id: User performing the update (must be a group member).
            updates: Dict of fields to patch — allowed: name, details, recurring_choice,
                     difficulty, estimated_mins, category, next_due, days_of_week, recur_value.
        Output:
            Updated TaskTemplate instance. Raises ValueError for auth failures.
        """
        template = TaskTemplate.objects.select_related('group').filter(id=template_id, active=True).first()
        if template is None:
            raise ValueError("Template not found.")
        if not GroupMembership.objects.filter(user_id=actor_id, group=template.group).exists():
            raise ValueError("Actor is not a member of this group.")

        allowed = {'name', 'details', 'recurring_choice', 'difficulty', 'estimated_mins',
                   'category', 'next_due', 'days_of_week', 'recur_value', 'importance',
                   'photo_proof_required'}
        update_fields = []
        for field, value in updates.items():
            if field in allowed:
                setattr(template, field, value)
                update_fields.append(field)
        if update_fields:
            template.full_clean()
            template.save(update_fields=update_fields)
        return template

    def delete_template(self, *, template_id: str, actor_id: str) -> None:
        """Soft-delete a template and transition pending occurrences to 'cancelled'.

        'cancelled' is a declared terminal status in TaskOccurrence.status_choices.
        Inputs:
            template_id: Template being removed.
            actor_id: User performing the action (must be a group member).
        Output:
            None. Raises ValueError if not found or actor lacks membership.
        """
        template = TaskTemplate.objects.select_related('group').filter(id=template_id, active=True).first()
        if template is None:
            raise ValueError("Template not found.")
        if not GroupMembership.objects.filter(user_id=actor_id, group=template.group).exists():
            raise ValueError("Actor is not a member of this group.")

        with transaction.atomic():
            template.active = False
            template.save(update_fields=['active'])
            TaskOccurrence.objects.filter(template=template, status='pending').update(status='cancelled')
