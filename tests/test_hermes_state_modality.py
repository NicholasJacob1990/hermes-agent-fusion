"""Schema v7: modality column on messages (text | voice) for voice browser client."""

from __future__ import annotations

import sqlite3

import pytest

from hermes_state import SessionDB


@pytest.fixture()
def db(tmp_path):
    db_path = tmp_path / "state.db"
    session_db = SessionDB(db_path=db_path)
    yield session_db
    session_db.close()


def test_append_message_defaults_to_text_modality(db):
    db.create_session(session_id="s1", source="web")
    db.append_message(session_id="s1", role="user", content="hi")
    msgs = db.get_messages("s1")
    assert len(msgs) == 1
    assert msgs[0]["modality"] == "text"


def test_append_message_accepts_voice_modality(db):
    db.create_session(session_id="s1", source="web")
    db.append_message(
        session_id="s1",
        role="assistant",
        content="olá",
        modality="voice",
    )
    msgs = db.get_messages("s1")
    assert msgs[0]["modality"] == "voice"


def test_migration_adds_modality_to_legacy_v6_db(tmp_path):
    """Simulate a v6 database, open it with current SessionDB, verify modality is added."""
    db_path = tmp_path / "legacy.db"

    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            user_id TEXT,
            model TEXT,
            model_config TEXT,
            system_prompt TEXT,
            parent_session_id TEXT REFERENCES sessions(id),
            started_at REAL NOT NULL,
            ended_at REAL,
            end_reason TEXT,
            message_count INTEGER NOT NULL DEFAULT 0,
            tool_call_count INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            title TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL REFERENCES sessions(id),
            role TEXT NOT NULL,
            content TEXT,
            tool_call_id TEXT,
            tool_calls TEXT,
            tool_name TEXT,
            timestamp REAL NOT NULL,
            token_count INTEGER,
            finish_reason TEXT,
            reasoning TEXT,
            reasoning_details TEXT,
            codex_reasoning_items TEXT
        );
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
        INSERT INTO schema_version (version) VALUES (6);
        INSERT INTO sessions (id, source, started_at) VALUES ('legacy', 'cli', 0);
        INSERT INTO messages (session_id, role, content, timestamp)
            VALUES ('legacy', 'user', 'old turn', 0);
        """
    )
    conn.commit()
    conn.close()

    db = SessionDB(db_path=db_path)
    try:
        msgs = db.get_messages("legacy")
        assert len(msgs) == 1
        assert msgs[0]["modality"] == "text"

        # New inserts on the migrated DB still work and can carry modality
        db.append_message(
            session_id="legacy",
            role="assistant",
            content="nova",
            modality="voice",
        )
        msgs = db.get_messages("legacy")
        assert msgs[-1]["modality"] == "voice"
    finally:
        db.close()
