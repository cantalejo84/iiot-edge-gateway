"""
Event log: ring buffer for important system events.
Only logs meaningful actions (connection tests, config apply, agent start/stop).
Does NOT log polling, auto-save, or browsing operations.
"""

import threading
from collections import deque
from datetime import datetime, timezone

_lock = threading.Lock()
_events = deque(maxlen=150)


def log(level, component, message, detail=None):
    """
    level:     "info" | "warning" | "error"
    component: "opcua" | "mqtt" | "telegraf" | "system"
    message:   short human-readable summary
    detail:    optional extra info (error traceback, endpoint, etc.)
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "component": component,
        "message": message,
    }
    if detail:
        entry["detail"] = str(detail)[:500]
    with _lock:
        _events.appendleft(entry)


def get_events(limit=100):
    with _lock:
        return list(_events)[:limit]


def clear():
    with _lock:
        _events.clear()
