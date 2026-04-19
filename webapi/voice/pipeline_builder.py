"""Build a Pipecat pipeline for a browser voice session.

Layout::

    FastAPIWebsocketTransport (input)
        ↓
    GeminiLiveLLMService (via create_gemini_live_service)
        ↓
    FastAPIWebsocketTransport (output)

The function tool `run_hermes_agent` attached to the Gemini service is
bound to the Hermes session supplied by the /ws/voice route. We wire that
by injecting an ``agent_factory`` on :class:`HermesPipecatBridge` that
ignores whatever ``session_id`` Gemini sends and always returns an agent
for our real session. That is why voice turns land in the same chat
conversation as typed turns — they share the session_id.
"""

from __future__ import annotations

from typing import Any, Callable, Tuple

from fastapi import WebSocket
from pipecat.pipeline.pipeline import Pipeline
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from agent.pipecat_bridge import (
    HermesPipecatBridge,
    HermesPipecatBridgeConfig,
    create_gemini_live_service,
)


def _make_agent_factory(hermes_session_id: str) -> Callable[..., Any]:
    """Return a factory that binds the AIAgent to ``hermes_session_id``.

    The factory signature matches :meth:`HermesPipecatBridge._default_agent_factory`
    so the bridge can drop it in unchanged. It silently discards any
    session_id that Gemini Live supplies via the function tool — Gemini
    should not be deciding conversation identity.
    """

    def factory(session_id: Any = None) -> Any:  # noqa: ARG001 - session_id ignored
        from run_agent import AIAgent

        return AIAgent(
            session_id=hermes_session_id,
            platform="pipecat",
        )

    return factory


def build_voice_pipeline(
    *,
    websocket: WebSocket,
    hermes_session_id: str,
) -> Tuple[Pipeline, FastAPIWebsocketTransport, HermesPipecatBridge]:
    """Assemble the Pipecat pipeline for a single browser voice call.

    Parameters
    ----------
    websocket:
        The upgraded FastAPI WebSocket for this call.
    hermes_session_id:
        The Hermes session the voice turns must join. Persisted turns go
        to SQLite tagged with ``modality='voice'`` so the chat UI can
        render them alongside typed turns.
    """
    params = FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        add_wav_header=False,
        # Gemini Live provides native VAD — disable Pipecat-side VAD so we
        # don't double-gate speech segments.
        vad_enabled=False,
    )

    transport = FastAPIWebsocketTransport(websocket=websocket, params=params)

    config = HermesPipecatBridgeConfig.from_hermes_config()
    bridge = HermesPipecatBridge(
        config=config,
        agent_factory=_make_agent_factory(hermes_session_id),
    )

    gemini_service = create_gemini_live_service(config=config, bridge=bridge)

    pipeline = Pipeline([transport.input(), gemini_service, transport.output()])
    return pipeline, transport, bridge
