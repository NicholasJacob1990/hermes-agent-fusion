#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$HOME/.hermes/hermes-agent}"
VENV_PY="$ROOT/venv/bin/python"
EXAMPLE="$ROOT/examples/pipecat_gemini_live_hermes_bot.py"
HERMES_ENV="${HERMES_ENV:-$HOME/.hermes/.env}"
RUN_EXAMPLE="${RUN_EXAMPLE:-0}"

if [[ ! -d "$ROOT" ]]; then
  echo "Hermes repo not found at: $ROOT" >&2
  exit 1
fi

if [[ ! -x "$VENV_PY" ]]; then
  echo "Hermes virtualenv python not found at: $VENV_PY" >&2
  exit 1
fi

cd "$ROOT"

echo "==> Installing Hermes with Pipecat extras"
uv pip install --python "$VENV_PY" -e '.[pipecat]'

echo "==> Checking Gemini key presence in ~/.hermes/.env"
if ! grep -Eq '^(GOOGLE_API_KEY|GEMINI_API_KEY)=' "$HERMES_ENV"; then
  echo "Missing GOOGLE_API_KEY/GEMINI_API_KEY in $HERMES_ENV" >&2
  echo "Get one at: https://aistudio.google.com/app/apikey" >&2
  exit 1
fi

echo "==> Verifying bridge imports"
"$VENV_PY" - <<'PY'
from agent.pipecat_bridge import create_gemini_live_service
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
print('bridge_ok', create_gemini_live_service.__name__, GeminiLiveLLMService.__name__)
PY

echo "==> Done"
echo "Example script: $EXAMPLE"
echo "Workspace voice settings: http://localhost:3000/settings (or your active workspace port)"

echo
if [[ "$RUN_EXAMPLE" == "1" ]]; then
  echo "==> Launching example via Pipecat runner"
  exec "$VENV_PY" "$EXAMPLE"
else
  echo "To run now:"
  echo "  RUN_EXAMPLE=1 $ROOT/scripts/bootstrap-pipecat-gemini-live.sh"
fi
