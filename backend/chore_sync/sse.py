import json
import queue
import threading
from typing import Any, Dict, Set


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


def publish(user_id: int, message: dict[str, Any]) -> None:
    with _lock:
        subs = list(_subscribers.get(user_id, set()))
    payload = json.dumps(message)
    for q in subs:
        try:
            q.put_nowait(payload)
        except Exception:
            continue
