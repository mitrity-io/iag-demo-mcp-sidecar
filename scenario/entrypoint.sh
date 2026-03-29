#!/bin/sh
set -e

# Validate required env vars.
for var in ANTHROPIC_API_KEY MITRITY_AGENT_KEY MITRITY_CONTROL_PLANE_URL MITRITY_AGENT_ID; do
    eval val=\$$var
    if [ -z "$val" ]; then
        echo "ERROR: $var is not set. See .env.example for required variables."
        exit 1
    fi
done

# Export sidecar version for the demo runner.
MITRITY_SIDECAR_VERSION="$(/usr/local/bin/mitrity-mcp-sidecar -version 2>/dev/null || echo "unknown")"
export MITRITY_SIDECAR_VERSION

# Render the sidecar config template with env vars.
envsubst < /etc/mitrity/sidecar.yaml.tmpl > /etc/mitrity/sidecar.yaml

echo "Sidecar config written to /etc/mitrity/sidecar.yaml"

exec python /app/scenario/runner.py "$@"
