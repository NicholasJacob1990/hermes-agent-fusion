import asyncio
import threading
import time

import pytest


@pytest.mark.asyncio
async def test_builds_expected_tool_schema():
    from agent.pipecat_bridge import build_hermes_function_tool

    tool = build_hermes_function_tool()

    assert tool["function_declarations"][0]["name"] == "run_hermes_agent"
    params = tool["function_declarations"][0]["parameters"]
    assert params["type"] == "object"
    assert set(params["required"]) == {"prompt"}
    assert "context" in params["properties"]


def test_system_instruction_forces_hermes_tool_usage():
    from agent.pipecat_bridge import build_system_instruction

    instruction = build_system_instruction(tool_name="run_hermes_agent")

    assert "run_hermes_agent" in instruction
    assert "Always call" in instruction
    assert "Do not answer from your own world knowledge" in instruction


@pytest.mark.asyncio
async def test_bridge_handler_runs_agent_and_returns_payload():
    from agent.pipecat_bridge import HermesPipecatBridge

    captured = {}

    class FakeAgent:
        def run_conversation(self, prompt, **kwargs):
            captured["prompt"] = prompt
            captured["kwargs"] = kwargs
            return {"final_response": "Resposta Hermes"}

    class FakeParams:
        function_name = "run_hermes_agent"
        tool_call_id = "tool-1"
        arguments = {
            "prompt": "Explique o diff",
            "context": "repo hermes-agent",
            "session_id": "voice-session-1",
        }
        llm = None
        context = None

        def __init__(self):
            self.result = None

        async def result_callback(self, result, **_kwargs):
            self.result = result

    bridge = HermesPipecatBridge(agent_factory=lambda session_id=None: FakeAgent())
    params = FakeParams()

    await bridge.handle_function_call(params)

    assert captured["prompt"] == "Explique o diff"
    assert captured["kwargs"]["task_id"] == "voice-session-1"
    assert captured["kwargs"]["persist_user_message"] == "Explique o diff"
    assert "repo hermes-agent" in captured["kwargs"]["system_message"]
    assert params.result["response"] == "Resposta Hermes"
    assert params.result["session_id"] == "voice-session-1"


def test_missing_prompt_is_rejected():
    from agent.pipecat_bridge import _normalize_tool_arguments

    with pytest.raises(ValueError, match="prompt"):
        _normalize_tool_arguments({"context": "sem prompt"})


def test_load_google_api_key_reads_hermes_env(tmp_path, monkeypatch):
    from agent.pipecat_bridge import load_google_api_key

    hermes_home = tmp_path / '.hermes'
    hermes_home.mkdir()
    (hermes_home / '.env').write_text('GOOGLE_API_KEY=test-google-key\n', encoding='utf-8')
    monkeypatch.setattr('agent.pipecat_bridge.Path.home', lambda: tmp_path)
    monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)

    assert load_google_api_key() == 'test-google-key'


@pytest.mark.asyncio
async def test_bridge_serializes_same_session_calls():
    from agent.pipecat_bridge import HermesPipecatBridge

    state = {"entered": False, "overlap": False}
    state_lock = threading.Lock()

    class FakeAgent:
        def run_conversation(self, prompt, **kwargs):
            with state_lock:
                if state["entered"]:
                    state["overlap"] = True
                state["entered"] = True
            time.sleep(0.05)
            with state_lock:
                state["entered"] = False
            return {"final_response": prompt}

    class FakeParams:
        llm = None
        context = None
        function_name = "run_hermes_agent"
        tool_call_id = "tool"

        def __init__(self, prompt):
            self.arguments = {"prompt": prompt, "session_id": "shared-session"}
            self.result = None

        async def result_callback(self, result, **_kwargs):
            self.result = result

    bridge = HermesPipecatBridge(agent_factory=lambda session_id=None: FakeAgent())
    first = FakeParams("primeiro")
    second = FakeParams("segundo")

    await asyncio.gather(
        bridge.handle_function_call(first),
        bridge.handle_function_call(second),
    )

    assert state["overlap"] is False


def test_bridge_uses_hermes_system_message_not_gemini_transport_instruction():
    from agent.pipecat_bridge import HermesPipecatBridge, HermesPipecatBridgeConfig

    bridge = HermesPipecatBridge(
        config=HermesPipecatBridgeConfig(
            gemini_system_instruction="ignored-on-gemini-side",
            hermes_system_message="only for Hermes",
        ),
        agent_factory=lambda session_id=None: object(),
    )

    system_message = bridge._build_system_message("contexto ativo")

    assert "only for Hermes" in system_message
    assert "ignored-on-gemini-side" not in system_message
    assert "contexto ativo" in system_message
