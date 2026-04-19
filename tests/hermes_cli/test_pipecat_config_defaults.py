from hermes_cli.config import DEFAULT_CONFIG


def test_default_config_includes_pipecat_bridge_settings():
    pipecat = DEFAULT_CONFIG.get("pipecat")

    assert isinstance(pipecat, dict)
    assert pipecat["tool_name"] == "run_hermes_agent"
    assert pipecat["gemini_live_model"]
    assert pipecat["gemini_live_voice"]
    assert "gemini_system_instruction" in pipecat
    assert "hermes_system_message" in pipecat
    assert isinstance(pipecat["agent"], dict)
    assert pipecat["agent"]["max_iterations"] == 90
