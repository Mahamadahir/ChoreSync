"""Household playbook orchestration for reusable multi-step routines."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlaybookService:
    """Coordinates template-driven playbooks that bundle tasks, automations, and guidance."""

    def create_playbook(self, *, creator_id: str, payload: dict) -> None:
        """Author a new playbook with steps, triggers, and default assignees."""
        # TODO: Validate schema, persist versioned steps, and emit discovery events.
        raise NotImplementedError("TODO: implement playbook creation")

    def update_playbook(self, *, playbook_id: str, updates: dict) -> None:
        """Modify an existing playbook definition."""
        # TODO: Enforce permissions, maintain version history, and broadcast changes.
        raise NotImplementedError("TODO: implement playbook update")

    def delete_playbook(self, *, playbook_id: str, actor_id: str) -> None:
        """Archive a playbook to prevent future activation."""
        # TODO: Soft-delete the record, detach scheduled automations, and note audit logs.
        raise NotImplementedError("TODO: implement playbook deletion")

    def list_playbooks(self, *, group_id: str | None = None) -> None:
        """Fetch available playbooks for a group or global catalog."""
        # TODO: Merge org-wide catalog entries with local drafts and apply filters.
        raise NotImplementedError("TODO: implement playbook listing")

    def activate_playbook(self, *, playbook_id: str, group_id: str, kickoff_context: dict | None = None) -> None:
        """Instantiate the playbook into live tasks and automations."""
        # TODO: Expand steps into tasks, schedule dependencies, and sync with TaskScheduler.
        raise NotImplementedError("TODO: implement playbook activation")

    def archive_completed_playbook(self, *, playbook_run_id: str) -> None:
        """Finalize and archive a completed playbook run."""
        # TODO: Aggregate metrics, snapshot outcomes, and surface insights dashboards.
        raise NotImplementedError("TODO: implement playbook archival flow")
