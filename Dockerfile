FROM --platform=linux/amd64 golang:1.26-alpine AS go-builder

WORKDIR /build
COPY go.mod ./
RUN go mod download
COPY cmd/ cmd/
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -trimpath -o /demo-tools ./cmd/demo-tools

# Pull the pre-built MCP Sidecar binary from the public ghcr.io image.
FROM --platform=linux/amd64 ghcr.io/mitrity-io/mitrity-mcp-sidecar:latest AS sidecar

FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext-base \
    && rm -rf /var/lib/apt/lists/*

COPY --from=go-builder /demo-tools /usr/local/bin/demo-tools
COPY --from=sidecar /mitrity-mcp-sidecar /usr/local/bin/mitrity-mcp-sidecar

COPY scenario/ /app/scenario/
COPY config/ /etc/mitrity/
COPY workspace/ /workspace/

RUN pip install --no-cache-dir -r /app/scenario/requirements.txt

WORKDIR /app
RUN chmod +x /app/scenario/entrypoint.sh

ENTRYPOINT ["/app/scenario/entrypoint.sh"]
