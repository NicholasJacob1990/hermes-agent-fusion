"""Gemini Live helpers for gateway voice-note workflows.

This module currently focuses on generating Telegram-ready voice replies from
Hermes text using Gemini Live native audio output. The gateway already handles
transport and STT; Gemini Live is used here as a higher-quality audio reply
engine for platforms where the user expects a spoken answer back.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from agent.pipecat_bridge import DEFAULT_GEMINI_MODEL, load_google_api_key

PCM_INPUT_MIME = "audio/pcm;rate=16000"
PCM_OUTPUT_RATE = 24000
DEFAULT_TELEGRAM_REPLY_PROMPT = (
    "Fale em português do Brasil, com naturalidade e de forma breve. "
    "Responda apenas com o conteúdo falado ao usuário."
)


def _resolve_live_model(model: Optional[str] = None) -> str:
    if model and model.strip():
        return model.strip()
    return DEFAULT_GEMINI_MODEL


def _ffmpeg_binary() -> str:
    ffmpeg = os.getenv("FFMPEG_BIN", "ffmpeg").strip() or "ffmpeg"
    return ffmpeg


def convert_audio_file_to_pcm16(audio_path: str) -> bytes:
    """Convert an audio file to raw PCM16 mono 16kHz for Gemini Live."""

    command = [
        _ffmpeg_binary(),
        "-nostdin",
        "-v",
        "error",
        "-i",
        audio_path,
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        "16000",
        "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg conversion failed: {stderr or 'unknown error'}")
    if not result.stdout:
        raise RuntimeError("ffmpeg conversion failed: empty PCM output")
    return bytes(result.stdout)


def _write_pcm_to_ogg_opus(pcm_bytes: bytes) -> str:
    """Convert raw 24k PCM output from Gemini Live into an OGG/Opus voice file."""

    pcm_fd, pcm_path = tempfile.mkstemp(prefix="gemini-live-reply-", suffix=".pcm")
    os.close(pcm_fd)
    ogg_fd, ogg_path = tempfile.mkstemp(prefix="gemini-live-reply-", suffix=".ogg")
    os.close(ogg_fd)
    Path(pcm_path).write_bytes(pcm_bytes)

    command = [
        _ffmpeg_binary(),
        "-nostdin",
        "-v",
        "error",
        "-f",
        "s16le",
        "-ar",
        str(PCM_OUTPUT_RATE),
        "-ac",
        "1",
        "-i",
        pcm_path,
        "-c:a",
        "libopus",
        "-b:a",
        "48k",
        "-y",
        ogg_path,
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    try:
        os.unlink(pcm_path)
    except OSError:
        pass
    if result.returncode != 0:
        try:
            os.unlink(ogg_path)
        except OSError:
            pass
        stderr = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg opus conversion failed: {stderr or 'unknown error'}")
    return ogg_path


async def synthesize_speech_via_gemini_live(
    text: str,
    *,
    model: Optional[str] = None,
    instruction: str = DEFAULT_TELEGRAM_REPLY_PROMPT,
) -> Dict[str, Any]:
    """Generate a Telegram-ready OGG/Opus voice reply using Gemini Live."""

    try:
        from google import genai
        from google.genai import types
    except Exception as exc:
        return {
            "success": False,
            "file_path": "",
            "error": f"google-genai not available: {exc}",
        }

    try:
        client = genai.Client(api_key=load_google_api_key())
        audio_chunks = bytearray()
        config = {
            "response_modalities": ["AUDIO"],
            "system_instruction": instruction,
        }

        async with client.aio.live.connect(
            model=_resolve_live_model(model),
            config=config,
        ) as session:
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text=text)],
                )
            )
            async for msg in session.receive():
                server_content = getattr(msg, "server_content", None)
                model_turn = getattr(server_content, "model_turn", None)
                if not model_turn:
                    continue
                for part in model_turn.parts or []:
                    inline_data = getattr(part, "inline_data", None)
                    if inline_data and getattr(inline_data, "data", None):
                        audio_chunks.extend(inline_data.data)

        if not audio_chunks:
            return {
                "success": False,
                "file_path": "",
                "error": "Gemini Live returned no audio",
            }

        file_path = await asyncio.to_thread(_write_pcm_to_ogg_opus, bytes(audio_chunks))
        return {
            "success": True,
            "file_path": file_path,
            "provider": "gemini-live",
        }
    except Exception as exc:
        return {
            "success": False,
            "file_path": "",
            "error": f"Gemini Live TTS failed: {exc}",
        }
