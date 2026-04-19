"""VoiceTurnFrameObserver forwards frames and mirrors transcription events."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    TranscriptionFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from webapi.voice.frame_observer import VoiceTurnFrameObserver


def _observer(persister):
    obs = VoiceTurnFrameObserver(persister)
    return obs


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def test_transcription_frame_feeds_user_buffer(loop):
    persister = MagicMock(spec=["on_user_transcription", "on_bot_transcription", "on_bot_started_speaking", "on_bot_stopped_speaking"])
    obs = _observer(persister)
    frame = TranscriptionFrame(text="olá mundo", user_id="", timestamp="")
    with patch.object(obs, "push_frame") as push:
        loop.run_until_complete(obs.process_frame(frame, FrameDirection.UPSTREAM))

    persister.on_user_transcription.assert_called_once_with("olá mundo")
    persister.on_bot_transcription.assert_not_called()
    push.assert_awaited_once_with(frame, FrameDirection.UPSTREAM)


def test_tts_text_frame_feeds_bot_buffer(loop):
    persister = MagicMock(spec=["on_user_transcription", "on_bot_transcription", "on_bot_started_speaking", "on_bot_stopped_speaking"])
    obs = _observer(persister)
    frame = TTSTextFrame(text="olá! ", aggregated_by="test")
    with patch.object(obs, "push_frame") as push:
        loop.run_until_complete(obs.process_frame(frame, FrameDirection.DOWNSTREAM))

    persister.on_bot_transcription.assert_called_once_with("olá! ")
    persister.on_user_transcription.assert_not_called()
    push.assert_awaited_once()


def test_bot_boundary_frames_trigger_flush_callbacks(loop):
    persister = MagicMock(spec=["on_user_transcription", "on_bot_transcription", "on_bot_started_speaking", "on_bot_stopped_speaking"])
    obs = _observer(persister)
    with patch.object(obs, "push_frame"):
        loop.run_until_complete(obs.process_frame(BotStartedSpeakingFrame(), FrameDirection.DOWNSTREAM))
        loop.run_until_complete(obs.process_frame(BotStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM))

    persister.on_bot_started_speaking.assert_called_once()
    persister.on_bot_stopped_speaking.assert_called_once()


def test_empty_text_is_not_forwarded_to_persister(loop):
    """Filters trivial no-text frames so the persister buffer stays clean."""
    persister = MagicMock(spec=["on_user_transcription", "on_bot_transcription", "on_bot_started_speaking", "on_bot_stopped_speaking"])
    obs = _observer(persister)

    with patch.object(obs, "push_frame"):
        loop.run_until_complete(obs.process_frame(TranscriptionFrame(text="", user_id="", timestamp=""), FrameDirection.UPSTREAM))
        loop.run_until_complete(obs.process_frame(TTSTextFrame(text="", aggregated_by="test"), FrameDirection.DOWNSTREAM))

    persister.on_user_transcription.assert_not_called()
    persister.on_bot_transcription.assert_not_called()


def test_unknown_frame_is_passed_through(loop):
    """Non-observed frames must still forward — pipeline integrity."""
    persister = MagicMock(spec=["on_user_transcription", "on_bot_transcription", "on_bot_started_speaking", "on_bot_stopped_speaking"])
    obs = _observer(persister)

    class CustomFrame(Frame):
        pass

    frame = CustomFrame()
    with patch.object(obs, "push_frame") as push:
        loop.run_until_complete(obs.process_frame(frame, FrameDirection.DOWNSTREAM))
    push.assert_awaited_once_with(frame, FrameDirection.DOWNSTREAM)
