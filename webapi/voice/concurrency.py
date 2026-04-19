"""Per-session in-memory lock for the Pipecat browser voice client.

Enforces one active voice call per Hermes session_id. A token returned
on acquire must be supplied on release, so a stale tab closing after the
lock was already re-acquired by a newer tab cannot free the wrong slot.

Keyed on session_id (not user_id) because the webapi is currently
single-user / local. When multi-user auth ships, migrate the key to a
tuple of (user_id, session_id) or (user_id,) depending on the desired
scope of the constraint.
"""

from __future__ import annotations

import threading
import uuid
from typing import Dict


class AlreadyActive(Exception):
    """Raised when a voice call is already active for the given key."""


class VoiceSessionLocks:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: Dict[str, str] = {}  # session_id -> token

    def acquire(self, session_id: str) -> str:
        with self._lock:
            if session_id in self._active:
                raise AlreadyActive(session_id)
            token = uuid.uuid4().hex
            self._active[session_id] = token
            return token

    def release(self, session_id: str, token: str) -> None:
        with self._lock:
            current = self._active.get(session_id)
            if current is not None and current == token:
                self._active.pop(session_id, None)


# Module-level singleton used by the WS route.
VOICE_LOCKS = VoiceSessionLocks()
