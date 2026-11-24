from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_HTTP_RESPONSE = "Request accepted and queued for processing."


@dataclass(frozen=True)
class ArgumentSpec:
    name: str
    type: str = "string"
    required: bool = True
    default: Any = None


@dataclass(frozen=True)
class StdioActionSpec:
    command: tuple[str, ...]
    env: dict[str, str]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    arguments: tuple[ArgumentSpec, ...]
    http_response: str
    stdio: StdioActionSpec | None = None


@dataclass(frozen=True)
class ServerSpec:
    server_name: str
    tools: tuple[ToolSpec, ...]
    spec_path: Path

    @property
    def package_name(self) -> str:
        return sanitize_identifier(self.server_name)


def load_server_spec(path: str | Path) -> ServerSpec:
    spec_path = Path(path).expanduser().resolve()
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    tools = data.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("spec field tools must be a non-empty list")
    return ServerSpec(
        server_name=_require_string(data, "server_name"),
        tools=tuple(_parse_tool(tool) for tool in tools),
        spec_path=spec_path,
    )


def sanitize_identifier(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    if not normalized:
        raise ValueError(f"cannot derive package identifier from {value!r}")
    if normalized[0].isdigit():
        normalized = f"mcp_{normalized}"
    return normalized


def python_type_name(argument_type: str) -> str:
    return {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
    }[argument_type]


def _parse_tool(data: Any) -> ToolSpec:
    if not isinstance(data, dict):
        raise ValueError("spec tools entries must be objects")
    arguments = data.get("arguments", [])
    if not isinstance(arguments, list):
        raise ValueError("spec tool arguments must be a list")
    return ToolSpec(
        name=_require_string(data, "name"),
        description=_require_string(data, "description"),
        arguments=tuple(_parse_argument(argument) for argument in arguments),
        http_response=str(data.get("http_response", DEFAULT_HTTP_RESPONSE)),
        stdio=_parse_stdio_action(data.get("stdio")),
    )


def _parse_argument(data: Any) -> ArgumentSpec:
    if not isinstance(data, dict):
        raise ValueError("spec tool arguments entries must be objects")
    argument_type = str(data.get("type", "string"))
    if argument_type not in {"string", "integer", "number", "boolean"}:
        raise ValueError(f"unsupported argument type: {argument_type}")
    return ArgumentSpec(
        name=_require_string(data, "name"),
        type=argument_type,
        required=bool(data.get("required", True)),
        default=data.get("default"),
    )


def _parse_stdio_action(data: Any) -> StdioActionSpec | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("spec tool stdio field must be an object")
    command = data.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        raise ValueError("spec tool stdio.command must be a non-empty string array")
    env = data.get("env", {})
    if not isinstance(env, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in env.items()):
        raise ValueError("spec tool stdio.env must be a string map")
    return StdioActionSpec(command=tuple(command), env=dict(env))


def _require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"spec field {key!r} must be a non-empty string")
    return value
