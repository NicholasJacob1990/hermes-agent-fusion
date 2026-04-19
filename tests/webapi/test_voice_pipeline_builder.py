"""Pipeline builder wiring for the /ws/voice route.

Verifies that build_voice_pipeline assembles
    Pipeline([transport.input(), gemini_service, transport.output()])
with a Gemini Live service created by create_gemini_live_service and a
HermesPipecatBridge whose agent_factory ignores Gemini's session_id and
always binds to the Hermes WS session_id provided by the route.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from webapi.voice.pipeline_builder import build_voice_pipeline


def test_build_voice_pipeline_wires_transport_gemini_output():
    websocket = MagicMock(name="websocket")

    with (
        patch(
            "webapi.voice.pipeline_builder.FastAPIWebsocketTransport"
        ) as MockTransport,
        patch(
            "webapi.voice.pipeline_builder.FastAPIWebsocketParams"
        ) as MockParams,
        patch(
            "webapi.voice.pipeline_builder.create_gemini_live_service"
        ) as mock_factory,
        patch(
            "webapi.voice.pipeline_builder.Pipeline"
        ) as MockPipeline,
    ):
        mock_transport = MagicMock(name="transport")
        mock_transport.input.return_value = "TRANSPORT_INPUT"
        mock_transport.output.return_value = "TRANSPORT_OUTPUT"
        MockTransport.return_value = mock_transport
        MockParams.return_value = "TRANSPORT_PARAMS"
        mock_factory.return_value = "GEMINI_SERVICE"
        MockPipeline.return_value = "PIPELINE"

        pipeline, transport, bridge = build_voice_pipeline(
            websocket=websocket,
            hermes_session_id="hermes-session-123",
        )

        # transport params: audio in + out enabled, vad disabled (Gemini VAD)
        MockParams.assert_called_once()
        params_kwargs = MockParams.call_args.kwargs
        assert params_kwargs["audio_in_enabled"] is True
        assert params_kwargs["audio_out_enabled"] is True
        assert params_kwargs["vad_enabled"] is False
        assert params_kwargs["add_wav_header"] is False

        # transport built with websocket + params
        MockTransport.assert_called_once_with(
            websocket=websocket, params="TRANSPORT_PARAMS"
        )

        # Gemini service built with our bridge
        mock_factory.assert_called_once()
        assert mock_factory.call_args.kwargs["bridge"] is bridge

        # Pipeline = [input, gemini, output] when no observer provided
        MockPipeline.assert_called_once_with(
            ["TRANSPORT_INPUT", "GEMINI_SERVICE", "TRANSPORT_OUTPUT"]
        )
        assert pipeline == "PIPELINE"
        assert transport is mock_transport


def test_observer_is_inserted_between_gemini_and_output():
    websocket = MagicMock(name="websocket")
    observer = MagicMock(name="observer")

    with (
        patch("webapi.voice.pipeline_builder.FastAPIWebsocketTransport") as MockTransport,
        patch("webapi.voice.pipeline_builder.FastAPIWebsocketParams"),
        patch("webapi.voice.pipeline_builder.create_gemini_live_service") as mock_factory,
        patch("webapi.voice.pipeline_builder.Pipeline") as MockPipeline,
    ):
        mock_transport = MagicMock()
        mock_transport.input.return_value = "IN"
        mock_transport.output.return_value = "OUT"
        MockTransport.return_value = mock_transport
        mock_factory.return_value = "GEMINI"

        build_voice_pipeline(
            websocket=websocket,
            hermes_session_id="s",
            observer=observer,
        )

        MockPipeline.assert_called_once_with(["IN", "GEMINI", observer, "OUT"])


def test_bridge_factory_binds_agent_to_hermes_session():
    """The bridge's agent_factory must return an agent bound to the Hermes
    WS session_id, regardless of what session_id Gemini supplies via its
    function-call argument.

    The bridge still keys its internal cache on Gemini's session_id (that
    is :meth:`HermesPipecatBridge.get_agent`'s contract), but the AIAgent
    returned by the factory is always bound to the Hermes session — so
    persisted turns land in the text chat's conversation.
    """
    fake_agent = MagicMock(name="fake_agent")
    bound_to = {}

    def fake_factory_creator(hermes_session_id: str):
        def factory(session_id=None):
            # Ignore Gemini's session_id; always bind to hermes_session_id.
            bound_to["hermes"] = hermes_session_id
            return fake_agent
        return factory

    with (
        patch("webapi.voice.pipeline_builder.FastAPIWebsocketTransport"),
        patch("webapi.voice.pipeline_builder.FastAPIWebsocketParams"),
        patch("webapi.voice.pipeline_builder.create_gemini_live_service"),
        patch("webapi.voice.pipeline_builder.Pipeline"),
        patch(
            "webapi.voice.pipeline_builder._make_agent_factory",
            side_effect=fake_factory_creator,
        ),
    ):
        _, _, bridge = build_voice_pipeline(
            websocket=MagicMock(),
            hermes_session_id="session-abc",
        )

    # Whatever session_id Gemini supplies, the agent comes back bound to ours.
    agent_for_gemini_a, _, _ = bridge.get_agent("gemini-wants-xyz")
    agent_for_gemini_b, _, _ = bridge.get_agent("gemini-wants-different")

    assert agent_for_gemini_a is fake_agent
    assert agent_for_gemini_b is fake_agent
    assert bound_to["hermes"] == "session-abc"
