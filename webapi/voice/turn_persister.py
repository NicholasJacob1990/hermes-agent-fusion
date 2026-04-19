"""Buffer Pipecat transcription deltas and flush completed turns to SQLite.

Gemini Live emits fine-grained end-of-sentence chunks for both user and
bot transcription. We accumulate those deltas and only persist when the
speaker boundary crosses — so a single persisted message represents one
full speaking turn, matching what a user of the typed chat sees.

Side-effects:
    SessionDB.append_message(session_id=..., role=..., content=...,
                             modality="voice")

Life-cycle:
    on_user_transcription(text)   — append to user buffer
    on_bot_transcription(text)    — append to bot buffer
    on_bot_started_speaking()     — flush user buffer (if non-empty)
    on_bot_stopped_speaking()     — flush bot buffer (if non-empty)
    on_disconnect()               — flush both sides (graceful shutdown)
"""

from __future__ import annotations

from typing import Any


class VoiceTurnPersister:
    def __init__(
        self,
        *,
        db: Any,
        session_id: str,
        voice_session_id: str,
    ) -> None:
        self._db = db
        self._session_id = session_id
        # voice_session_id is retained for log correlation even though we
        # don't currently persist it alongside the row — useful when
        # tracing a specific call across stdout/metrics. Upgrade path: add
        # a dedicated metadata column if the correlation needs to survive
        # reload.
        self._voice_session_id = voice_session_id
        self._user_buffer: list[str] = []
        self._bot_buffer: list[str] = []

    def on_user_transcription(self, text: str) -> None:
        self._user_buffer.append(text)

    def on_bot_transcription(self, text: str) -> None:
        self._bot_buffer.append(text)

    def on_bot_started_speaking(self) -> None:
        self._flush_user()

    def on_bot_stopped_speaking(self) -> None:
        self._flush_bot()

    def on_disconnect(self) -> None:
        # Flush whichever side still holds content — covers graceful close
        # and the case where the WS drops mid-turn before a clean boundary.
        self._flush_user()
        self._flush_bot()

    # ── internals ────────────────────────────────────────────────────

    def _flush_user(self) -> None:
        content = "".join(self._user_buffer).strip()
        self._user_buffer.clear()
        if not content:
            return
        self._db.append_message(
            session_id=self._session_id,
            role="user",
            content=content,
            modality="voice",
        )

    def _flush_bot(self) -> None:
        content = "".join(self._bot_buffer).strip()
        self._bot_buffer.clear()
        if not content:
            return
        self._db.append_message(
            session_id=self._session_id,
            role="assistant",
            content=content,
            modality="voice",
        )
