"""VoiceTurnPersister: buffers user/bot transcription deltas, flushes to SessionDB."""

from __future__ import annotations

from unittest.mock import MagicMock

from webapi.voice.turn_persister import VoiceTurnPersister


def test_user_turn_flushed_when_bot_starts_speaking():
    db = MagicMock(name="session_db")
    p = VoiceTurnPersister(db=db, session_id="s1", voice_session_id="vs-1")

    p.on_user_transcription("olá")
    p.on_user_transcription(" mundo")
    p.on_bot_started_speaking()

    db.append_message.assert_called_once()
    kwargs = db.append_message.call_args.kwargs
    assert kwargs["session_id"] == "s1"
    assert kwargs["role"] == "user"
    assert kwargs["content"] == "olá mundo"
    assert kwargs["modality"] == "voice"


def test_bot_turn_flushed_when_bot_stops_speaking():
    db = MagicMock(name="session_db")
    p = VoiceTurnPersister(db=db, session_id="s1", voice_session_id="vs-1")

    p.on_user_transcription("oi")
    p.on_bot_started_speaking()  # flushes user
    p.on_bot_transcription("olá! ")
    p.on_bot_transcription("como posso ajudar?")
    p.on_bot_stopped_speaking()  # flushes bot

    assert db.append_message.call_count == 2
    first, second = db.append_message.call_args_list
    assert first.kwargs["role"] == "user"
    assert first.kwargs["content"] == "oi"
    assert second.kwargs["role"] == "assistant"
    assert second.kwargs["content"] == "olá! como posso ajudar?"
    assert second.kwargs["modality"] == "voice"


def test_empty_buffer_does_not_flush():
    db = MagicMock(name="session_db")
    p = VoiceTurnPersister(db=db, session_id="s1", voice_session_id="vs-1")
    # Bot boundary with nothing buffered on the user side — no flush.
    p.on_bot_started_speaking()
    p.on_bot_stopped_speaking()
    db.append_message.assert_not_called()


def test_on_disconnect_flushes_pending_buffers():
    """Graceful shutdown: whatever is in the buffer gets persisted so it
    survives a reload even if the bot never emitted a clean boundary."""
    db = MagicMock(name="session_db")
    p = VoiceTurnPersister(db=db, session_id="s1", voice_session_id="vs-1")

    # Pending user text that never reached the bot boundary
    p.on_user_transcription("mensagem interrompida")
    p.on_disconnect()

    db.append_message.assert_called_once()
    kwargs = db.append_message.call_args.kwargs
    assert kwargs["role"] == "user"
    assert kwargs["content"] == "mensagem interrompida"
    assert kwargs["modality"] == "voice"


def test_content_is_trimmed_before_persistence():
    """Whitespace-only flushes are dropped; leading/trailing whitespace
    around real content is stripped."""
    db = MagicMock(name="session_db")
    p = VoiceTurnPersister(db=db, session_id="s1", voice_session_id="vs-1")

    p.on_user_transcription("  \n")
    p.on_bot_started_speaking()  # only whitespace → no flush
    assert db.append_message.call_count == 0

    p.on_bot_transcription("  resposta com padding  ")
    p.on_bot_stopped_speaking()
    assert db.append_message.call_count == 1
    assert db.append_message.call_args.kwargs["content"] == "resposta com padding"
