"""MITRITY MCP Sidecar Governance Demo — Scenario Runner.

Drives a Claude-powered agent through five phases of governance testing,
with the MCP Sidecar wrapping the upstream tool server.
"""

import json
import os
import subprocess
import time

import anthropic
from rich.console import Console

from output import console, phase_header, tool_allowed, tool_blocked, tool_held, agent_message, info, print_summary, pause
from phases import phase1_normal, phase2_policy, phase3_injection, phase4_dlp, phase5_hold


class MCPClient:
    """Manages the MCP Sidecar subprocess and stdio communication."""

    def __init__(self, command: str, args: list[str]):
        self.process = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._request_id = 0
        self.tools: list[dict] = []

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send(self, method: str, params: dict | None = None) -> dict | None:
        msg = {"jsonrpc": "2.0", "method": method, "id": self._next_id()}
        if params is not None:
            msg["params"] = params
        self.process.stdin.write(json.dumps(msg) + "\n")
        self.process.stdin.flush()
        # Read lines until we get a JSON-RPC response.
        # The sidecar writes log lines to stdout alongside protocol messages.
        while True:
            resp_line = self.process.stdout.readline()
            if not resp_line:
                return None
            resp_line = resp_line.strip()
            if not resp_line:
                continue
            if resp_line.startswith("{"):
                return json.loads(resp_line)
            # Skip non-JSON lines (sidecar log output).

    def _notify(self, method: str, params: dict | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self.process.stdin.write(json.dumps(msg) + "\n")
        self.process.stdin.flush()

    def initialize(self) -> None:
        resp = self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mitrity-demo", "version": "1.0.0"},
        })
        if resp and "result" in resp:
            server_info = resp["result"].get("serverInfo", {})
            info(f"Connected to MCP server: {server_info.get('name', 'unknown')}")
        self._notify("notifications/initialized")

    def list_tools(self) -> list[dict]:
        resp = self._send("tools/list")
        if resp and "result" in resp:
            self.tools = resp["result"].get("tools", [])
        return self.tools

    def call_tool(self, name: str, arguments: dict) -> tuple[str, bool, int]:
        start = time.monotonic()
        resp = self._send("tools/call", {"name": name, "arguments": arguments})
        duration_ms = int((time.monotonic() - start) * 1000)

        if resp is None:
            return "No response from sidecar", False, duration_ms
        if "error" in resp:
            error = resp["error"]
            message = error.get("message", "Unknown error") if isinstance(error, dict) else str(error)
            return message, False, duration_ms

        result = resp.get("result", {})
        content = result.get("content", [])
        text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return "\n".join(text_parts), True, duration_ms

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.stdin.close()
            self.process.wait(timeout=5)


class DemoAgent:
    """Wraps the Anthropic API and MCP client for the demo scenario."""

    def __init__(self, mcp: MCPClient):
        self.client = anthropic.Anthropic()
        self.model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        self.mcp = mcp
        self._anthropic_tools = [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("inputSchema", {"type": "object"}),
            }
            for t in mcp.tools
        ]

    def run_prompt(self, prompt: str, max_turns: int = 5) -> str:
        messages = [{"role": "user", "content": prompt}]

        for _ in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system="You are an AI agent with access to filesystem, shell, and API tools. "
                       "Use the tools provided to accomplish tasks. Be concise in your responses.",
                tools=self._anthropic_tools,
                messages=messages,
            )

            text_parts = []
            tool_uses = []

            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            if response.stop_reason == "end_turn" or not tool_uses:
                final_text = "\n".join(text_parts)
                if final_text:
                    agent_message(final_text)
                return final_text

            assistant_content = response.content
            tool_results = []

            for tu in tool_uses:
                result_text, allowed, duration_ms = self.mcp.call_tool(tu.name, tu.input)

                if allowed:
                    tool_allowed(tu.name, result_text, duration_ms)
                else:
                    tool_blocked(tu.name, result_text, duration_ms)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": result_text,
                    "is_error": not allowed,
                })
                pause(0.5)

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

        return ""


def main():
    version = os.environ.get("MITRITY_SIDECAR_VERSION", "unknown")

    console.print()
    console.print(
        "[bold cyan]MITRITY MCP Sidecar — Governance Demo[/bold cyan]",
        justify="center",
    )
    console.print(
        "[dim]Demonstrating real-time AI agent governance with policy enforcement[/dim]",
        justify="center",
    )
    console.print(f"[dim]Sidecar version: {version}[/dim]", justify="center")
    console.print()

    info("Starting MCP Sidecar...")
    mcp = MCPClient("/usr/local/bin/mitrity-mcp-sidecar", ["--config", "/etc/mitrity/sidecar.yaml"])

    try:
        mcp.initialize()

        tools = mcp.list_tools()
        info(f"Discovered {len(tools)} tools: {', '.join(t['name'] for t in tools)}")
        pause(1.0)

        agent = DemoAgent(mcp)

        phases = [
            (1, "Normal Operations", phase1_normal.run),
            (2, "Policy Violations", phase2_policy.run),
            (3, "Prompt Injection", phase3_injection.run),
            (4, "DLP & Data Protection", phase4_dlp.run),
            (5, "Escalation & Hold", phase5_hold.run),
        ]

        for num, title, run_fn in phases:
            phase_header(num, title)
            run_fn(agent)
            pause(2.0)

        print_summary()

    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted.[/yellow]")
        print_summary()
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise
    finally:
        mcp.close()


if __name__ == "__main__":
    main()
