"""Pipecat ↔ Hermes bridge for Gemini Live voice sessions.

This module keeps Hermes as the agent/tool-using brain while Pipecat +
Gemini Live handle real-time voice transport, VAD, and audio I/O.

The integration pattern is intentionally simple:
- Gemini Live receives the user's speech
- Gemini Live is instructed to call a single Hermes function tool
- The tool callback runs a Hermes AIAgent turn
- The tool result is returned to Gemini Live for spoken delivery

Everything is optional and lazy-imported so the core Hermes install does not
require Pipecat unless the bridge is actually used.
"""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional


DEFAULT_TOOL_NAME = "run_hermes_agent"
DEFAULT_GEMINI_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_GEMINI_VOICE = "Charon"
DEFAULT_SESSION_PREFIX = "pipecat-gemini-live"


@dataclass(slots=True)
class HermesPipecatBridgeConfig:
    """Runtime settings for the Pipecat/Gemini Live bridge."""

    tool_name: str = DEFAULT_TOOL_NAME
    gemini_model: str = DEFAULT_GEMINI_MODEL
    gemini_voice: str = DEFAULT_GEMINI_VOICE
    tool_timeout_secs: float = 300.0
    session_prefix: str = DEFAULT_SESSION_PREFIX
    hermes_model: str = ""
    hermes_provider: str = ""
    hermes_toolsets: list[str] = field(default_factory=list)
    hermes_max_iterations: int = 90
    quiet_mode: bool = True
    gemini_system_instruction: str = ""
    hermes_system_message: str = ""

    @classmethod
    def from_hermes_config(cls) -> "HermesPipecatBridgeConfig":
        try:
            from hermes_cli.config import load_config

            config = load_config() or {}
        except Exception:
            config = {}

        bridge_cfg = config.get("pipecat", {}) if isinstance(config, dict) else {}
        bridge_agent_cfg = bridge_cfg.get("agent", {}) if isinstance(bridge_cfg, dict) else {}

        toolsets = bridge_agent_cfg.get("toolsets", [])
        if not isinstance(toolsets, list):
            toolsets = []

        return cls(
            tool_name=str(bridge_cfg.get("tool_name") or DEFAULT_TOOL_NAME),
            gemini_model=str(bridge_cfg.get("gemini_live_model") or DEFAULT_GEMINI_MODEL),
            gemini_voice=str(bridge_cfg.get("gemini_live_voice") or DEFAULT_GEMINI_VOICE),
            tool_timeout_secs=float(bridge_cfg.get("tool_timeout_secs") or 300.0),
            session_prefix=str(bridge_cfg.get("session_prefix") or DEFAULT_SESSION_PREFIX),
            hermes_model=str(bridge_agent_cfg.get("model") or ""),
            hermes_provider=str(bridge_agent_cfg.get("provider") or ""),
            hermes_toolsets=[str(tool) for tool in toolsets if str(tool).strip()],
            hermes_max_iterations=int(bridge_agent_cfg.get("max_iterations") or 90),
            quiet_mode=bool(bridge_agent_cfg.get("quiet_mode", True)),
            gemini_system_instruction=str(bridge_cfg.get("gemini_system_instruction") or ""),
            hermes_system_message=str(bridge_cfg.get("hermes_system_message") or ""),
        )


def load_google_api_key() -> str:
    """Return the configured Google/Gemini API key or raise a helpful error."""

    try:
        from dotenv import load_dotenv
        load_dotenv(Path.home() / '.hermes' / '.env', override=False)
    except Exception:
        pass

    api_key = (os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")).strip()
    if api_key:
        return api_key
    raise ValueError("Missing GOOGLE_API_KEY or GEMINI_API_KEY for Gemini Live")


def build_hermes_function_tool(tool_name: str = DEFAULT_TOOL_NAME) -> Dict[str, Any]:
    """Build a provider-native Gemini function declaration for Hermes turns."""

    return {
        "function_declarations": [
            {
                "name": tool_name,
                "description": (
                    "Delegate the user's spoken request to Hermes Agent so Hermes can "
                    "reason, use tools, and return the final answer for voice playback."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "The user's request transcript, normalized for Hermes.",
                        },
                        "context": {
                            "type": "string",
                            "description": (
                                "Optional extra context for Hermes, such as transport/session "
                                "state, UI metadata, or the active app view."
                            ),
                        },
                        "session_id": {
                            "type": "string",
                            "description": (
                                "Stable voice session identifier so multiple turns can reuse "
                                "the same Hermes conversation."
                            ),
                        },
                    },
                    "required": ["prompt"],
                },
            }
        ]
    }


def build_system_instruction(
    *,
    tool_name: str = DEFAULT_TOOL_NAME,
    base_instruction: str = "",
) -> str:
    """System instruction that keeps Gemini Live in transport/facilitator mode."""

    guidance = (
        f"You are the real-time voice front-end for Hermes Agent. "
        f"Always call `{tool_name}` for user requests that need an answer, action, or reasoning. "
        "Do not answer from your own world knowledge when Hermes should handle the task. "
        "You may keep acknowledgements extremely brief, but all substantive responses must come from Hermes. "
        "Preserve the user's language when you pass the prompt to Hermes, and return the Hermes result faithfully."
    )
    if base_instruction.strip():
        return f"{base_instruction.strip()}\n\n{guidance}"
    return guidance


def _normalize_tool_arguments(arguments: Dict[str, Any]) -> Dict[str, str]:
    prompt = str(arguments.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")

    context = str(arguments.get("context") or "").strip()
    session_id = str(arguments.get("session_id") or "").strip()

    return {
        "prompt": prompt,
        "context": context,
        "session_id": session_id,
    }


class HermesPipecatBridge:
    """Adapter that turns Pipecat function calls into Hermes agent turns."""

    def __init__(
        self,
        *,
        config: Optional[HermesPipecatBridgeConfig] = None,
        agent_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.config = config or HermesPipecatBridgeConfig.from_hermes_config()
        self._agent_factory = agent_factory or self._default_agent_factory
        self._agents: dict[str, Any] = {}
        self._session_locks: dict[str, threading.Lock] = {}

    def _default_agent_factory(self, session_id: Optional[str] = None):
        from run_agent import AIAgent

        kwargs: Dict[str, Any] = {
            "session_id": session_id,
            "platform": "pipecat",
            "quiet_mode": self.config.quiet_mode,
            "max_iterations": self.config.hermes_max_iterations,
        }
        if self.config.hermes_model:
            kwargs["model"] = self.config.hermes_model
        if self.config.hermes_provider:
            kwargs["provider"] = self.config.hermes_provider
        if self.config.hermes_toolsets:
            kwargs["enabled_toolsets"] = list(self.config.hermes_toolsets)
        return AIAgent(**kwargs)

    def _session_key(self, requested_session_id: str) -> str:
        if requested_session_id:
            return requested_session_id
        return f"{self.config.session_prefix}-default"

    def get_agent(self, requested_session_id: str = ""):
        session_key = self._session_key(requested_session_id)
        if session_key not in self._agents:
            self._agents[session_key] = self._agent_factory(session_id=session_key)
        if session_key not in self._session_locks:
            self._session_locks[session_key] = threading.Lock()
        return self._agents[session_key], session_key, self._session_locks[session_key]

    def _build_system_message(self, context: str) -> Optional[str]:
        parts = []
        if self.config.hermes_system_message.strip():
            parts.append(self.config.hermes_system_message.strip())
        if context.strip():
            parts.append(f"Pipecat voice-session context:\n{context.strip()}")
        if not parts:
            return None
        return "\n\n".join(parts)

    async def handle_function_call(self, params: Any) -> None:
        args = _normalize_tool_arguments(dict(getattr(params, "arguments", {}) or {}))
        agent, session_key, session_lock = self.get_agent(args["session_id"])
        system_message = self._build_system_message(args["context"])

        def _run_turn() -> Any:
            with session_lock:
                return agent.run_conversation(
                    args["prompt"],
                    system_message=system_message,
                    task_id=session_key,
                    persist_user_message=args["prompt"],
                )

        result = await asyncio.to_thread(_run_turn)
        if isinstance(result, dict):
            response_text = str(result.get("final_response") or "").strip()
        else:
            response_text = str(result or "").strip()

        payload = {
            "response": response_text,
            "session_id": session_key,
        }
        await params.result_callback(payload)


def create_gemini_live_service(
    *,
    config: Optional[HermesPipecatBridgeConfig] = None,
    bridge: Optional[HermesPipecatBridge] = None,
    api_key: Optional[str] = None,
    system_instruction: str = "",
    tools: Optional[Iterable[Dict[str, Any]]] = None,
    **kwargs: Any,
):
    """Create a Pipecat Gemini Live service pre-wired to Hermes.

    This function is lazy-imported so Hermes can ship without Pipecat. The
    returned object is a ``GeminiLiveLLMService`` ready for use in a Pipecat
    pipeline.
    """

    try:
        from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise ImportError(
            "Pipecat is not installed. Install the optional extra with: "
            'pip install "hermes-agent[pipecat]"'
        ) from exc

    config = config or HermesPipecatBridgeConfig.from_hermes_config()
    bridge = bridge or HermesPipecatBridge(config=config)
    effective_tools = list(tools) if tools is not None else [build_hermes_function_tool(config.tool_name)]
    effective_instruction = build_system_instruction(
        tool_name=config.tool_name,
        base_instruction=system_instruction or config.gemini_system_instruction,
    )

    service = GeminiLiveLLMService(
        api_key=api_key or load_google_api_key(),
        model=config.gemini_model,
        voice_id=config.gemini_voice,
        system_instruction=effective_instruction,
        tools=effective_tools,
        inference_on_context_initialization=False,
        **kwargs,
    )
    service.register_function(
        config.tool_name,
        bridge.handle_function_call,
        timeout_secs=config.tool_timeout_secs,
    )
    return service
