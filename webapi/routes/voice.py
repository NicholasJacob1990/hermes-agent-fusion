"""WebSocket endpoint for the Pipecat browser voice client.

    GET /ws/voice?session_id=<existing hermes session id>

The route assembles a Pipecat voice pipeline (Gemini Live as the realtime
brain; the run_hermes_agent function tool delegates to the same Hermes
session the typed chat uses), observes transcription frames through a
VoiceTurnFrameObserver, and persists completed turns with
``modality='voice'`` so the chat UI can render them with a 🎙️ prefix.

Gating (in order):
    1. HERMES_VOICE_BROWSER_ENABLED — close 1008 if off
    2. session_id must resolve via SessionDB — close 1008 if not
    3. No existing voice call for that session_id — close 1013 if taken
    4. Pipecat pipeline build — close 1011 on failure

The pipeline lifecycle is owned by the endpoint; the lock is always
released in ``finally``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, status
from starlette.websockets import WebSocketDisconnect

from hermes_state import SessionDB
from webapi.deps import get_session_db, is_voice_browser_enabled
from webapi.voice.concurrency import VOICE_LOCKS, AlreadyActive
from webapi.voice.frame_observer import VoiceTurnFrameObserver
from webapi.voice.pipeline_builder import build_voice_pipeline
from webapi.voice.turn_persister import VoiceTurnPersister

log = logging.getLogger(__name__)
router = APIRouter(tags=["voice"])


@router.websocket("/ws/voice")
async def voice_ws(
    websocket: WebSocket,
    session_id: Annotated[str, Query(...)],
    session_db: Annotated[SessionDB, Depends(get_session_db)],
) -> None:
    # 1. Feature flag: close before accepting, so there's no protocol upgrade.
    if not is_voice_browser_enabled():
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="voice-disabled"
        )
        return

    # 2. Session must already exist (the voice turn joins an existing chat).
    if session_db.get_session(session_id) is None:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="session-not-found"
        )
        return

    # 3. One active voice call per session_id.
    try:
        lock_token = VOICE_LOCKS.acquire(session_id)
    except AlreadyActive:
        await websocket.close(code=1013, reason="voice-already-active")
        return

    voice_session_id = uuid.uuid4().hex
    await websocket.accept()
    log.info(
        "voice.ws.start session=%s voice_session=%s",
        session_id,
        voice_session_id,
    )

    persister = VoiceTurnPersister(
        db=session_db,
        session_id=session_id,
        voice_session_id=voice_session_id,
    )
    try:
        await _run_pipeline(
            websocket=websocket,
            hermes_session_id=session_id,
            persister=persister,
        )
    except WebSocketDisconnect:
        # Normal browser-side disconnect; no stack trace noise.
        log.debug("voice.ws.disconnect voice_session=%s", voice_session_id)
    except Exception:
        log.exception("voice.ws.error voice_session=%s", voice_session_id)
    finally:
        persister.on_disconnect()
        VOICE_LOCKS.release(session_id, lock_token)
        log.info("voice.ws.end voice_session=%s", voice_session_id)
        # Close explicitly so clients learn the call ended promptly. The
        # starlette TestClient in particular blocks on receive until the
        # server side emits a close. Pipecat's own transport may also have
        # closed already; guard against double-close.
        try:
            await websocket.close()
        except RuntimeError:
            pass


async def _run_pipeline(
    *,
    websocket: WebSocket,
    hermes_session_id: str,
    persister: VoiceTurnPersister,
) -> None:
    """Build and drive the Pipecat pipeline.

    Kept as a separate function so the WS route can mock it in tests
    without pulling Pipecat's full runtime into the unit-test path.
    """
    # Local imports so the ROUTE module is cheap to import for tests that
    # never touch Pipecat (flag-off, missing-session, concurrency paths).
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineTask

    observer = VoiceTurnFrameObserver(persister)
    pipeline_obj, _transport, _bridge = build_voice_pipeline(
        websocket=websocket,
        hermes_session_id=hermes_session_id,
        observer=observer,
    )
    task = PipelineTask(pipeline_obj)
    await PipelineRunner().run(task)
