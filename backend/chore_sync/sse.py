import json
import queue
import threading
import time
from typing import Any, Dict, NamedTuple, Set


class Event(NamedTuple):
    """A single SSE event ready for wire serialisation."""
    event_id: str   # value for the SSE `id:` line
    payload: str    # pre-serialised JSON string


_subscribers: Dict[int, Set[queue.Queue]] = {}
_lock = threading.Lock()


def subscribe(user_id: int) -> queue.Queue:
    q: queue.Queue = queue.Queue()
    with _lock:
        _subscribers.setdefault(user_id, set()).add(q)
    return q


def unsubscribe(user_id: int, q: queue.Queue) -> None:
    with _lock:
        subs = _subscribers.get(user_id)
        if subs is None:
            return
        subs.discard(q)
        if not subs:
            _subscribers.pop(user_id, None)


def publish(user_id: int, message: dict[str, Any], event_id: str | None = None) -> None:
    """Publish a message to all active SSE subscribers for user_id.

    event_id: stable identifier for this event.  Pass the DB Notification.id
    (as a string) for notification events so the client can use Last-Event-ID
    to resume from the correct position after a reconnect.  Defaults to a
    millisecond timestamp prefixed with 'ts-' for ephemeral events (e.g.
    calendar_sync) that don't have a DB record.
    """
    eid = event_id or f"ts-{int(time.time() * 1000)}"
    payload = json.dumps(message)
    ev = Event(event_id=eid, payload=payload)
    with _lock:
        subs = list(_subscribers.get(user_id, set()))
    for q in subs:
        try:
            q.put_nowait(ev)
        except Exception:
            continue
