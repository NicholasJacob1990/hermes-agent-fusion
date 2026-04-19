---
title: "Bridge Gemini Live + Pipecat to Hermes"
description: "Use Pipecat and Gemini Live as the realtime voice layer while Hermes remains the downstream agent brain."
---

# Bridge Gemini Live + Pipecat to Hermes

Hermes now includes an optional bridge module at `agent.pipecat_bridge` for teams that want:

- **Pipecat** handling realtime media transport / VAD
- **Gemini Live** handling low-latency voice I/O
- **Hermes** staying in charge of reasoning, tools, memory, and agent workflows

## Install

```bash
pip install "hermes-agent[pipecat]"
# or, inside the Hermes repo:
./scripts/bootstrap-pipecat-gemini-live.sh
```

You also need a Google AI Studio key:

```bash
export GOOGLE_API_KEY=your-key
# or
export GEMINI_API_KEY=your-key
```

## Config

Optional defaults live under `pipecat` in `~/.hermes/config.yaml`:

```yaml
pipecat:
  tool_name: run_hermes_agent
  gemini_live_model: models/gemini-2.5-flash-native-audio-preview-12-2025
  gemini_live_voice: Charon
  tool_timeout_secs: 300
  session_prefix: pipecat-gemini-live
  gemini_system_instruction: ""
  hermes_system_message: ""
  agent:
    model: ""
    provider: ""
    toolsets: []
    max_iterations: 90
    quiet_mode: true
```

Leave `agent.model` / `agent.provider` empty to inherit your normal Hermes defaults.
Use `gemini_system_instruction` for transport/orchestration behavior on the Gemini Live side, and `hermes_system_message` for extra per-turn guidance that should be injected into Hermes itself.

## Usage in a Pipecat bot

You can either wire the bridge into your own Pipecat pipeline, or start from the included example:

```bash
source venv/bin/activate
python examples/pipecat_gemini_live_hermes_bot.py
```

Custom integration:

```python
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from agent.pipecat_bridge import create_gemini_live_service

# Assume `transport` is your existing Pipecat transport (Daily, Twilio, etc.)
llm = create_gemini_live_service()
context = OpenAILLMContext(messages=[])
context_aggregator = llm.create_context_aggregator(context)

pipeline = [
    transport.input(),
    context_aggregator.user(),
    llm,
    context_aggregator.assistant(),
    transport.output(),
]
```

The bridge configures Gemini Live with a single function tool: `run_hermes_agent`.
When the user speaks:

1. Gemini Live transcribes the utterance
2. Gemini Live calls the Hermes bridge tool
3. Hermes runs a normal `AIAgent.run_conversation(...)` turn
4. The tool result is returned to Gemini Live
5. Gemini Live speaks the Hermes answer back to the user

## What Hermes keeps doing

The downstream Hermes turn still supports the usual agent behavior:

- tool calling
- memory/session continuity
- profiles and model routing
- skills
- session IDs per voice conversation

## Module surface

### `build_hermes_function_tool()`
Returns the Gemini function declaration used for delegation.

### `build_system_instruction()`
Builds the Gemini-side instruction that forces substantive requests through Hermes.

### `HermesPipecatBridge`
Caches Hermes agents by session ID and handles Pipecat function callbacks.

### `create_gemini_live_service()`
Creates a `GeminiLiveLLMService` pre-wired to the Hermes bridge.

## Notes

- This bridge is **optional** and does not change Hermes CLI voice mode.
- Pipecat is lazy-imported, so the base Hermes install stays lightweight.
- If you want custom transport logic, instantiate `HermesPipecatBridge` directly and register its callback yourself.
