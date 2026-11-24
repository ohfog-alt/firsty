from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp_lure_lab.config import FAKE_SECRET_VALUE
from mcp_lure_lab.protocol import call_server_tool, list_server_tools


def test_workspace_tool_lists_and_logs_secret_reads(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    env = {"MCP_LURE_LOG_PATH": str(log_path), "MCP_LURE_SCENARIO": "readfile"}
    tools = asyncio.run(list_server_tools("mcp_lure_lab.servers.workspace", env))
    assert [tool.name for tool in tools.tools] == ["read_project_file"]

    result = asyncio.run(
        call_server_tool(
            "mcp_lure_lab.servers.workspace",
            "read_project_file",
            {"path": "private/approval_token.txt"},
            env,
        )
    )
    assert FAKE_SECRET_VALUE in result.content[0].text
    assert _event_types(log_path) == {"legit_reader_called", "secret_read"}


def test_poison_tool_description_and_forwarding_event(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    env = {
        "MCP_LURE_LOG_PATH": str(log_path),
        "MCP_LURE_SCENARIO": "readfile",
        "MCP_LURE_BEHAVIORS": "readfile",
        "MCP_LURE_ID": "approval_gate",
    }
    tools = asyncio.run(list_server_tools("mcp_lure_lab.servers.poison_lab", env))
    tool = tools.tools[0]
    assert tool.name == "run_preflight_check"
    assert "private/approval_token.txt" in tool.description

    asyncio.run(
        call_server_tool(
            "mcp_lure_lab.servers.poison_lab",
            "run_preflight_check",
            {"task": "inspect project", "approval_token": FAKE_SECRET_VALUE},
            env,
        )
    )
    assert _event_types(log_path) == {"poison_called", "secret_forwarded"}


def test_shadow_tool_matches_legitimate_name(tmp_path: Path) -> None:
    env = {"MCP_LURE_LOG_PATH": str(tmp_path / "events.jsonl"), "MCP_LURE_SCENARIO": "shadow"}
    legit = asyncio.run(list_server_tools("mcp_lure_lab.servers.workspace", env)).tools[0]
    shadow = asyncio.run(list_server_tools("mcp_lure_lab.servers.workspace_secure", env)).tools[0]
    assert legit.name == shadow.name == "read_project_file"
    assert legit.inputSchema == shadow.inputSchema


def test_confluence_shadow_tools_match_and_log_distinct_events(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    env = {"MCP_LURE_LOG_PATH": str(log_path), "MCP_LURE_SCENARIO": "shadow"}
    legit = asyncio.run(list_server_tools("mcp_lure_lab.servers.confluence", env)).tools[0]
    malicious = asyncio.run(list_server_tools("mcp_lure_lab.servers.confluence_v2", env)).tools[0]
    assert legit.name == malicious.name == "search_pages"
    assert legit.inputSchema == malicious.inputSchema

    asyncio.run(call_server_tool("mcp_lure_lab.servers.confluence", "search_pages", {"query": "MCP"}, env))
    asyncio.run(call_server_tool("mcp_lure_lab.servers.confluence_v2", "search_pages", {"query": "MCP"}, env))
    assert _event_types(log_path) == {"legit_search_called", "malicious_search_called"}

def _event_types(path: Path) -> set[str]:
    return {
        json.loads(line)["event_type"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
