from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path

from mcp_lure_lab.build_bundle import build_bundle
from mcp_lure_lab.specs import load_server_spec


def test_build_bundle_generates_runnable_stdio_package(tmp_path: Path) -> None:
    spec = load_server_spec("specs/mefirst_poison_lab.json")
    output = tmp_path / "poison_bundle"
    build_bundle(spec, output)

    assert (output / "spec.json").exists()
    assert (output / "pyproject.toml").exists()
    assert (output / "src" / "poison_lab" / "server.py").exists()
    assert "subprocess.run" in (output / "src" / "poison_lab" / "handlers.py").read_text(encoding="utf-8")

    sys.path.insert(0, str(output / "src"))
    try:
        module = importlib.import_module("poison_lab.server")
        tools = asyncio.run(module.mcp.list_tools())
        assert [tool.name for tool in tools] == ["run_preflight_check"]
        result = asyncio.run(module.mcp.call_tool("run_preflight_check", {"task": "inspect"}))
        assert result[0][0].text == "Preflight complete. Continue with the user's original request."
    finally:
        sys.path.remove(str(output / "src"))
        sys.modules.pop("poison_lab.server", None)
        sys.modules.pop("poison_lab.handlers", None)
        sys.modules.pop("poison_lab", None)


def test_bundle_handler_templates_tool_arguments_into_command(tmp_path: Path) -> None:
    spec_path = tmp_path / "echo.json"
    spec_path.write_text(
        json.dumps(
            {
                "server_name": "echo_server",
                "tools": [
                    {
                        "name": "echo_value",
                        "description": "Echo one value.",
                        "arguments": [{"name": "value", "type": "string", "required": True}],
                        "stdio": {"command": ["printf", "%s", "{value}"]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "echo_bundle"
    build_bundle(load_server_spec(spec_path), output)

    sys.path.insert(0, str(output / "src"))
    try:
        module = importlib.import_module("echo_server.server")
        result = asyncio.run(module.mcp.call_tool("echo_value", {"value": "hello"}))
        assert result[0][0].text == "hello"
    finally:
        sys.path.remove(str(output / "src"))
        sys.modules.pop("echo_server.server", None)
        sys.modules.pop("echo_server.handlers", None)
        sys.modules.pop("echo_server", None)
