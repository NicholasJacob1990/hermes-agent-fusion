"""Pipecat FrameProcessor that feeds transcription events to a VoiceTurnPersister.

Placement in the pipeline: AFTER gemini_service and BEFORE transport.output().
That way it sees:
  • TranscriptionFrame flowing UPSTREAM (user speech Gemini captured)
  • TTSTextFrame flowing DOWNSTREAM (bot response text)
  • BotStartedSpeakingFrame / BotStoppedSpeakingFrame (turn boundaries)

The observer is passive — it always forwards frames so the downstream
transport still gets everything it needs for audio playback.
"""

from __future__ import annotations

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    TranscriptionFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from webapi.voice.turn_persister import VoiceTurnPersister


class VoiceTurnFrameObserver(FrameProcessor):
    """FrameProcessor adapter that forwards frames untouched while mirroring
    user/bot transcription events into the persister."""

    def __init__(self, persister: VoiceTurnPersister) -> None:
        super().__init__()
        self._persister = persister

    async def process_frame(
        self, frame: Frame, direction: FrameDirection
    ) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = getattr(frame, "text", "") or ""
            if text:
                self._persister.on_user_transcription(text)
        elif isinstance(frame, TTSTextFrame):
            text = getattr(frame, "text", "") or ""
            if text:
                self._persister.on_bot_transcription(text)
        elif isinstance(frame, BotStartedSpeakingFrame):
            self._persister.on_bot_started_speaking()
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._persister.on_bot_stopped_speaking()

        await self.push_frame(frame, direction)
