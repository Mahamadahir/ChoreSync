"""Task-related API endpoints."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/")
async def create_task_endpoint() -> None:
    """Accept payloads for creating a new task.

    TODO: Validate request body, delegate to TaskScheduler.schedule_task, and return a
    resource representation once persistence succeeds.
    """
    raise NotImplementedError("TODO: implement task creation endpoint")


@router.post("/reassign")
async def reassign_overdue_tasks_endpoint() -> None:
    """Trigger overdue task reassignment for a group.

    TODO: Extract group identifiers, call TaskScheduler.reassign_overdue_tasks, and craft
    an audit-friendly response for the client.
    """
    raise NotImplementedError("TODO: implement overdue task reassignment endpoint")


@router.post("/recurrence")
async def generate_recurring_tasks_endpoint() -> None:
    """Generate future instances for a recurring task.

    TODO: Authorize the requester, call TaskScheduler.generate_recurring_instances, and
    enqueue calendar sync jobs for impacted members.
    """
    raise NotImplementedError("TODO: implement recurring task generation endpoint")
