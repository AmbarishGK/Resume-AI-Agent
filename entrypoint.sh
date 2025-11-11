#!/usr/bin/env bash
set -euo pipefail

# Configurable via env vars
: "${OLLAMA_HOST:=0.0.0.0:11434}"
: "${OLLAMA_MODELS:=}"         # space-separated list, e.g.: "mistral:instruct phi3:mini"
: "${HEALTH_URL:=http://localhost:11434/api/tags}"
: "${HEALTH_TIMEOUT:=60}"      # seconds to wait for Ollama ready

echo "[entrypoint] Starting Ollama at ${OLLAMA_HOST} ..."
nohup ollama serve >/tmp/ollama.log 2>&1 &

# Wait for API
echo -n "[entrypoint] Waiting for Ollama API"
SECS=0
until curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; do
  sleep 1
  SECS=$((SECS+1))
  echo -n "."
  if [ "$SECS" -ge "$HEALTH_TIMEOUT" ]; then
    echo
    echo "[entrypoint] ERROR: Ollama did not become ready within ${HEALTH_TIMEOUT}s"
    echo "Last log lines:"
    tail -n 50 /tmp/ollama.log || true
    exit 1
  fi
done
echo " ready in ${SECS}s."

# Optional pre-pull of models into the mounted volume
if [ -n "${OLLAMA_MODELS}" ]; then
  echo "[entrypoint] Pre-pulling models: ${OLLAMA_MODELS}"
  for m in ${OLLAMA_MODELS}; do
    echo " -> pulling ${m}"
    if ! ollama pull "${m}"; then
      echo "[entrypoint] WARNING: failed to pull ${m} (continuing)"
    fi
  done
fi

# Show available models
echo "[entrypoint] Available models:"
curl -s "${HEALTH_URL}" | jq -r '.models[].name' || true

echo "[entrypoint] Handing off to: $*"
exec "$@"
