# MITRITY MCP Sidecar — Governance Demo

Self-contained Docker demo that runs a Claude-powered AI agent through a scripted governance scenario using the MITRITY MCP Sidecar. The sidecar wraps an existing MCP tool server and intercepts every tool call for policy evaluation.

## Prerequisites

- Docker Desktop (or any Docker runtime)
- A MITRITY account with an active tenant
- An Anthropic API key

## Dashboard Setup

Before running the demo, configure these in your MITRITY dashboard:

### 1. Register an agent

Create an agent (e.g., "demo-agent") with mission scope "workspace file management and system operations". Copy the **Agent ID** (UUID) and the **Agent Key** (`ak_...`).

### 2. Create policies

| Policy | Type | Pattern | Scope |
|--------|------|---------|-------|
| Allow workspace reads | allow | `read_file` | path starts with `/workspace` |
| Allow workspace writes | allow | `write_file` | path starts with `/workspace` |
| Allow safe commands | allow | `run_command` | `ls`, `pwd`, `cat`, `echo`, `whoami` |
| Block system files | deny | `read_file`, `delete_file` | path outside `/workspace` |
| Block destructive commands | deny | `run_command` | `rm`, `curl`, `wget`, `nc`, `chmod` |
| Block dangerous SQL | deny | `query_database` | contains `DROP`, `DELETE`, `TRUNCATE` |
| Hold production deploys | hold | `call_api` | url contains "production" |

Also enable:
- **Prompt injection detection** (global setting)
- **DLP** with PII and credential patterns

## Quick Start

```bash
git clone git@github.com:mitrity-io/iag-demo-mcp-sidecar.git
cd iag-demo-mcp-sidecar
cp .env.example .env

# Edit .env with your ANTHROPIC_API_KEY and MITRITY_AGENT_KEY

docker compose up --build
```

## What the Demo Does

The demo runs five phases (~10 minutes total):

**Phase 1 — Normal Operations**: Read files, list directories, run safe commands, call APIs. All allowed.

**Phase 2 — Policy Violations**: Read system files, run destructive commands, dangerous SQL. All blocked with reason.

**Phase 3 — Prompt Injection**: Process "user input" with embedded injection payloads. Detected and blocked.

**Phase 4 — DLP & Data Protection**: Write files with API keys, send PII in notifications. DLP blocks exfiltration.

**Phase 5 — Escalation & Hold**: Attempt production deployment. Hold policy pauses action for dashboard approval.

> **Delegation chains and threat intelligence** are demonstrated in a separate, multi-container demo at [iag-demo-multi-agent](https://github.com/mitrity-io/iag-demo-multi-agent). That demo runs three governed agents in parallel containers (orchestrator + two workers) and produces real worker-to-worker delegation hops and threat-intel matches against the built-in indicator catalog. Pro/Enterprise plan required.

## Architecture

```
Docker Container
└── Python scenario runner (Claude Agent SDK)
    └── MCP Sidecar (governance wrapper)
        └── demo-tools (MCP server with all tools)
            ├── read_file, write_file, list_directory, delete_file
            ├── run_command
            └── call_api, query_database, send_notification
```

The sidecar connects to your MITRITY control plane via HTTPS for policy evaluation, event reporting, and heartbeat.

## Gateway vs Sidecar

Both binaries share the same governance core. Threat intelligence, delegation chains, DLP, prompt injection detection, ML drift scoring, and hold/approval workflows all run identically in either deployment — they're implemented in a shared `internal/interceptor` package. The architectural difference is **where each sits in the MCP request path**:

| | MCP Sidecar (this demo) | [MCP Gateway](https://github.com/mitrity-io/iag-demo-mcp-gateway) |
|---|---|---|
| **Role** | Transparent proxy in front of one existing MCP server | Is the MCP server, aggregating many sources |
| **Tool sources** | Single upstream subprocess | Multiple upstreams + native HTTP tools defined in config |
| **MCP protocol** | Passes through unchanged; intercepts only `tools/call` | Owns the catalog, applies namespace prefixes (`fs:read_file`, `shell:run_command`) |
| **Best for** | Retrofitting governance onto an existing MCP server without changing the agent | Aggregating many tool sources behind one governed endpoint |

> **Credential broker injection** is on the roadmap for both binaries with hot rotation as a day-one feature. See [credential-injection-plan-2026-05-25.md](https://github.com/mitrity-io/iag-config/blob/main/credential-injection-plan-2026-05-25.md) for the sprint plan. Today, both binaries perform credential checkout and decryption via the broker; injection into outbound tool calls is partly wired (gateway native HTTP only) and lands fully in Sprints 3–4.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude |
| `MITRITY_AGENT_KEY` | Yes | Agent key from dashboard |
| `MITRITY_CONTROL_PLANE_URL` | Yes | Control plane URL |
| `MITRITY_AGENT_ID` | Yes | Agent UUID from dashboard |
| `MITRITY_DEMO_SPEED` | No | `normal` (default) or `fast` |
| `ANTHROPIC_MODEL` | No | Claude model (default: `claude-sonnet-4-20250514`) |
