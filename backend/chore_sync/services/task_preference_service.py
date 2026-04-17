"""Service for managing user task preferences (prefer / neutral / avoid)."""
from __future__ import annotations

from dataclasses import dataclass

from chore_sync.models import GroupMembership, TaskPreference, TaskTemplate


@dataclass
class TaskPreferenceService:

    VALID_PREFERENCES = frozenset({'prefer', 'neutral', 'avoid'})

    def set_preference(
        self,
        *,
        user,
        template: TaskTemplate,
        preference: str,
    ) -> TaskPreference:
        """Set or update a user's preference for a task template.

        Inputs:
            user: The user whose preference is being set.
            template: The TaskTemplate to set a preference on.
            preference: One of 'prefer', 'neutral', 'avoid'.
        Output:
            The created or updated TaskPreference instance.
            Raises ValueError for an invalid preference value.
            Raises PermissionError if the user is not a member of the template's group.
        """
        if preference not in self.VALID_PREFERENCES:
            raise ValueError(
                f"Invalid preference '{preference}'. Must be one of: "
                f"{', '.join(sorted(self.VALID_PREFERENCES))}."
            )
        if not GroupMembership.objects.filter(user=user, group=template.group).exists():
            raise PermissionError("You are not a member of this group.")

        obj, _ = TaskPreference.objects.update_or_create(
            user=user,
            task_template=template,
            defaults={"preference": preference},
        )
        return obj
