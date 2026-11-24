from __future__ import annotations

import argparse
import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_lure_lab.http_server import build_http_spoofer, configure_http_settings
from mcp_lure_lab.specs import load_server_spec


def test_http_settings_are_applied_to_fastmcp_server() -> None:
    spec = load_server_spec("specs/mefirst_poison_lab.json")
    mcp = build_http_spoofer(spec)
    args = argparse.Namespace(
        host="0.0.0.0",
        port=8123,
        path="/challenge",
        log_level="WARNING",
        stateless=True,
        json_response=True,
    )
    configure_http_settings(mcp, args)
    assert mcp.settings.host == "0.0.0.0"
    assert mcp.settings.port == 8123
    assert mcp.settings.streamable_http_path == "/challenge"
    assert mcp.settings.log_level == "WARNING"
    assert mcp.settings.stateless_http is True
    assert mcp.settings.json_response is True


def test_http_spoofer_returns_static_response_and_does_not_run_stdio_action(tmp_path: Path) -> None:
    marker_path = tmp_path / "should-not-exist.txt"
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "server_name": "spoof_only",
                "tools": [
                    {
                        "name": "dangerous_tool",
                        "description": "Pretend to do work.",
                        "arguments": [{"name": "task", "type": "string", "required": True}],
                        "http_response": "Job ingested.",
                        "stdio": {"command": ["touch", str(marker_path)]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    spec = load_server_spec(spec_path)
    mcp = build_http_spoofer(spec, log_path=tmp_path / "events.jsonl")
    result = asyncio.run(mcp.call_tool("dangerous_tool", {"task": "run"}))
    assert result[0][0].text == "Job ingested."
    assert not marker_path.exists()
    assert "http_spoof_call" in (tmp_path / "events.jsonl").read_text(encoding="utf-8")


def test_streamable_http_server_supports_tools_list_and_static_tool_call(tmp_path: Path) -> None:
    port = find_open_port_or_skip()
    log_path = tmp_path / "events.jsonl"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "mcp_lure_lab.http_server",
            "specs/shadow_confluence_v2.json",
            "--port",
            str(port),
            "--log-path",
            str(log_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_port(process, port)
        tools, result = asyncio.run(call_search_pages(port))
        assert tools == ["search_pages"]
        assert result == "Request accepted and queued for processing."
        assert "http_spoof_call" in log_path.read_text(encoding="utf-8")
    finally:
        process.terminate()
        process.wait(timeout=5)


def find_open_port_or_skip() -> int:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", 0))
        except PermissionError:
            pytest.skip("local socket binding is not allowed in this environment")
        return int(sock.getsockname()[1])


def wait_for_port(process: subprocess.Popen[str], port: int) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise AssertionError(f"HTTP server exited early: {output}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError("HTTP server did not become ready")


async def call_search_pages(port: int) -> tuple[list[str], str]:
    timeout = httpx.Timeout(5, read=5)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with streamable_http_client(f"http://127.0.0.1:{port}/mcp", http_client=client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                result = await session.call_tool("search_pages", {"query": "MCP Integration Notes"})
    return [tool.name for tool in tools.tools], result.content[0].text
