"""Root FastAPI application wiring for the ChoreSync backend."""
from __future__ import annotations

from fastapi import FastAPI

from chore_sync.api import calendar_router, group_router, task_router

# Register routers eagerly; dependency injection wiring will replace this later.
app = FastAPI(title="ChoreSync API", version="0.0.1-dev")

app.include_router(calendar_router.router)
app.include_router(group_router.router)
app.include_router(task_router.router)


@app.on_event("startup")
async def bootstrap_runtime_dependencies() -> None:
    """Prepare shared resources such as database pools, caches, and schedulers.

    TODO: Implement non-blocking initialization that pre-warms resource pools and
    registers background workers so request latency stays low from the first user action.
    """
    raise NotImplementedError("TODO: wire bootstrap routine once infrastructure is defined")


@app.on_event("shutdown")
async def teardown_runtime_dependencies() -> None:
    """Release shared resources gracefully when the service stops.

    TODO: Flush pending jobs, persist in-memory state, and emit structured shutdown logs
    to keep the platform observable during deploys and outages.
    """
    raise NotImplementedError("TODO: tear down resources when shutting down the app")


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    """Expose a lightweight readiness probe for Kubernetes and uptime monitors.

    TODO: Aggregate component-level diagnostics (database, message queue, calendar
    providers) and return a structured payload describing their status.
    """
    raise NotImplementedError("TODO: implement health check response with dependency status")
