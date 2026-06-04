"""Lightweight in-process event bus for per-workflow SSE streaming.

Agents call emit() as they start/complete. The SSE endpoint reads get_events().
No circular imports — both API and agents import this module.
"""
from datetime import datetime, timezone

_queues: dict[str, list[dict]] = {}


def register(workflow_id: str) -> None:
    _queues[workflow_id] = []


def emit(workflow_id: str, event_type: str, data: dict) -> None:
    if workflow_id not in _queues:
        _queues[workflow_id] = []
    _queues[workflow_id].append({
        "type": event_type,
        "ts": datetime.now(timezone.utc).isoformat(),
        "data": data,
    })


def get_events(workflow_id: str) -> list[dict]:
    return _queues.get(workflow_id, [])


def cleanup(workflow_id: str) -> None:
    _queues.pop(workflow_id, None)
