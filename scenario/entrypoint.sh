#!/bin/sh
set -e

# Validate required env vars.
for var in ANTHROPIC_API_KEY MITRITY_EDGE_API_KEY MITRITY_CONTROL_PLANE_URL MITRITY_EDGE_NODE_ID MITRITY_AGENT_ID; do
    eval val=\$$var
    if [ -z "$val" ]; then
        echo "ERROR: $var is not set. See .env.example for required variables."
        exit 1
    fi
done

# Render the sidecar config template with env vars.
envsubst < /etc/mitrity/sidecar.yaml.tmpl > /etc/mitrity/sidecar.yaml

echo "Sidecar config written to /etc/mitrity/sidecar.yaml"

exec python /app/scenario/runner.py "$@"
