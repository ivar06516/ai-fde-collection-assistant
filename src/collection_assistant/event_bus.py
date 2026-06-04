"""Lightweight in-process event bus for per-workflow SSE streaming.

Agents call emit() as they start/complete. The SSE endpoint reads get_events().
No circular imports — both API and agents import this module.
"""
import threading
from collections import defaultdict
from datetime import datetime, timezone

# M-1 fix: defaultdict prevents register/emit race; thread lock prevents concurrent eviction
_lock = threading.Lock()
_queues: defaultdict[str, list[dict]] = defaultdict(list)
_MAX_COMPLETED_WORKFLOWS = 200  # M-2 fix: cap memory growth


def register(workflow_id: str) -> None:
    with _lock:
        _queues[workflow_id] = []
        # Evict oldest entries if over cap
        if len(_queues) > _MAX_COMPLETED_WORKFLOWS:
            oldest = next(iter(_queues))
            del _queues[oldest]


def emit(workflow_id: str, event_type: str, data: dict) -> None:
    entry = {
        "type": event_type,
        "ts": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    with _lock:
        _queues[workflow_id].append(entry)


def get_events(workflow_id: str) -> list[dict]:
    with _lock:
        return list(_queues.get(workflow_id, []))


def cleanup(workflow_id: str) -> None:
    with _lock:
        _queues.pop(workflow_id, None)
