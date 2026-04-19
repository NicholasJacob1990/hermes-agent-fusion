"""/ws/voice endpoint — gating + lifecycle.

These tests mock ``webapi.routes.voice._run_pipeline`` so we exercise the
route's control flow without spinning up a real Pipecat runner.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from webapi.app import app
from webapi.deps import get_session_db
from webapi.voice.concurrency import VOICE_LOCKS


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient with a temp SessionDB injected via FastAPI's dependency
    override mechanism. Resets the voice lock registry so each test starts
    clean."""
    from hermes_state import SessionDB

    # Reset shared state between tests
    VOICE_LOCKS._active.clear()

    db = SessionDB(db_path=tmp_path / "state.db")

    def _override_db():
        return db

    app.dependency_overrides[get_session_db] = _override_db
    try:
        yield TestClient(app), db
    finally:
        app.dependency_overrides.pop(get_session_db, None)
        db.close()


def test_voice_ws_closes_when_flag_off(monkeypatch, client):
    monkeypatch.delenv("HERMES_VOICE_BROWSER_ENABLED", raising=False)
    tc, _ = client
    with pytest.raises(WebSocketDisconnect) as exc:
        with tc.websocket_connect("/ws/voice?session_id=s1"):
            pass
    assert exc.value.code == 1008


def test_voice_ws_closes_when_session_missing(monkeypatch, client):
    monkeypatch.setenv("HERMES_VOICE_BROWSER_ENABLED", "true")
    tc, _ = client
    with pytest.raises(WebSocketDisconnect) as exc:
        with tc.websocket_connect("/ws/voice?session_id=does-not-exist"):
            pass
    assert exc.value.code == 1008


def test_voice_ws_accepts_when_flag_on_and_session_exists(monkeypatch, client):
    """Happy path: pipeline is mocked, route runs through accept + release."""
    monkeypatch.setenv("HERMES_VOICE_BROWSER_ENABLED", "true")
    tc, db = client
    db.create_session(session_id="s1", source="web")

    with patch(
        "webapi.routes.voice._run_pipeline", new_callable=AsyncMock
    ) as mock_run:
        mock_run.return_value = None
        # _run_pipeline returns immediately; the server then closes. The
        # client block exits normally when that happens.
        with pytest.raises(WebSocketDisconnect):
            with tc.websocket_connect("/ws/voice?session_id=s1") as ws:
                ws.receive_text()

    mock_run.assert_awaited_once()
    # Lock must be released after the call ends
    assert "s1" not in VOICE_LOCKS._active


def test_voice_ws_rejects_concurrent_same_session(monkeypatch, client):
    monkeypatch.setenv("HERMES_VOICE_BROWSER_ENABLED", "true")
    tc, db = client
    db.create_session(session_id="s1", source="web")

    # Pre-acquire the lock so the next connect must be rejected with 1013
    VOICE_LOCKS._active["s1"] = "existing-token"

    with pytest.raises(WebSocketDisconnect) as exc:
        with tc.websocket_connect("/ws/voice?session_id=s1"):
            pass
    assert exc.value.code == 1013


def test_voice_ws_releases_lock_on_pipeline_error(monkeypatch, client):
    monkeypatch.setenv("HERMES_VOICE_BROWSER_ENABLED", "true")
    tc, db = client
    db.create_session(session_id="s1", source="web")

    async def _boom(**kwargs):
        raise RuntimeError("pipeline exploded")

    with patch("webapi.routes.voice._run_pipeline", side_effect=_boom):
        with pytest.raises(WebSocketDisconnect):
            with tc.websocket_connect("/ws/voice?session_id=s1") as ws:
                ws.receive_text()

    # Even after a pipeline exception, the lock must not remain held.
    assert "s1" not in VOICE_LOCKS._active
