"""VoiceSessionLocks: one active voice call per session_id, token-guarded release."""

from __future__ import annotations

import pytest

from webapi.voice.concurrency import AlreadyActive, VoiceSessionLocks


def test_first_acquire_succeeds():
    locks = VoiceSessionLocks()
    token = locks.acquire("s1")
    assert isinstance(token, str) and token


def test_second_acquire_same_session_rejects():
    locks = VoiceSessionLocks()
    locks.acquire("s1")
    with pytest.raises(AlreadyActive):
        locks.acquire("s1")


def test_release_allows_reacquire():
    locks = VoiceSessionLocks()
    token = locks.acquire("s1")
    locks.release("s1", token)
    assert locks.acquire("s1")


def test_different_sessions_are_independent():
    locks = VoiceSessionLocks()
    assert locks.acquire("s1")
    assert locks.acquire("s2")


def test_release_with_wrong_token_is_noop():
    locks = VoiceSessionLocks()
    locks.acquire("s1")
    locks.release("s1", token="wrong")
    # Original lock must still be held
    with pytest.raises(AlreadyActive):
        locks.acquire("s1")


def test_release_unknown_session_is_noop():
    # Covers the "disconnect after forced release" path in the WS route
    locks = VoiceSessionLocks()
    locks.release("does-not-exist", token="whatever")  # should not raise
