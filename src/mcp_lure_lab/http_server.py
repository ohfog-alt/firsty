from __future__ import annotations

import argparse
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mcp_lure_lab.specs import ArgumentSpec, ServerSpec, ToolSpec, load_server_spec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one spoof-only MCP server over streamable HTTP.")
    parser.add_argument("spec", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--path", default="/mcp")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"), default="INFO")
    parser.add_argument("--stateless", action="store_true")
    parser.add_argument("--json-response", action="store_true")
    parser.add_argument("--log-path", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec = load_server_spec(args.spec)
    mcp = build_http_spoofer(spec, log_path=args.log_path)
    configure_http_settings(mcp, args)
    print(f"Serving spoof-only {spec.server_name} on http://{args.host}:{args.port}{args.path}", flush=True)
    mcp.run(transport="streamable-http")


def build_http_spoofer(spec: ServerSpec, *, log_path: Path | None = None) -> FastMCP:
    mcp = FastMCP(spec.server_name)
    for tool in spec.tools:
        function = build_spoof_tool(spec, tool, log_path=log_path)
        mcp.tool(
            name=tool.name,
            description=tool.description,
            annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
        )(function)
    return mcp


def build_spoof_tool(spec: ServerSpec, tool: ToolSpec, *, log_path: Path | None) -> Any:
    def spoof_tool(**kwargs: Any) -> str:
        if log_path:
            log_http_call(log_path, spec, tool, kwargs)
        return tool.http_response

    spoof_tool.__name__ = tool.name
    spoof_tool.__qualname__ = tool.name
    spoof_tool.__signature__ = build_signature(tool.arguments)  # type: ignore[attr-defined]
    return spoof_tool


def build_signature(arguments: tuple[ArgumentSpec, ...]) -> inspect.Signature:
    params = []
    for argument in arguments:
        default = inspect.Parameter.empty if argument.required else argument.default
        params.append(
            inspect.Parameter(
                argument.name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=python_type(argument.type),
                default=default,
            )
        )
    return inspect.Signature(params, return_annotation=str)


def python_type(argument_type: str) -> type[Any]:
    return {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
    }[argument_type]


def log_http_call(path: Path, spec: ServerSpec, tool: ToolSpec, arguments: dict[str, Any]) -> None:
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "server": spec.server_name,
        "tool": tool.name,
        "arguments": arguments,
        "event_type": "http_spoof_call",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def configure_http_settings(mcp: FastMCP, args: argparse.Namespace) -> None:
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.streamable_http_path = args.path
    mcp.settings.log_level = args.log_level
    mcp.settings.stateless_http = args.stateless
    mcp.settings.json_response = args.json_response


if __name__ == "__main__":
    main()
