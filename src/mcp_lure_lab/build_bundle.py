from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from mcp_lure_lab.specs import ServerSpec, ToolSpec, load_server_spec, python_type_name, sanitize_identifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a standalone stdio MCP server bundle from one spec.")
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec = load_server_spec(args.spec)
    output = args.output.expanduser().resolve()
    build_bundle(spec, output, force=args.force)
    print(f"Generated stdio bundle at {output}")


def build_bundle(spec: ServerSpec, output: Path, *, force: bool = False) -> None:
    if output.exists():
        if not force:
            raise FileExistsError(f"output already exists: {output}")
        shutil.rmtree(output)
    package_root = output / "src" / spec.package_name
    package_root.mkdir(parents=True)
    shutil.copy2(spec.spec_path, output / "spec.json")
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "server.py").write_text(render_server_py(spec), encoding="utf-8")
    (package_root / "handlers.py").write_text(render_handlers_py(spec), encoding="utf-8")
    (output / "pyproject.toml").write_text(render_pyproject(spec), encoding="utf-8")
    (output / "README.md").write_text(render_bundle_readme(spec), encoding="utf-8")


def render_pyproject(spec: ServerSpec) -> str:
    dist_name = spec.server_name.replace("_", "-")
    return f"""[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "{dist_name}-mcp"
version = "0.1.0"
description = "Generated MCP stdio server bundle for {spec.server_name}."
requires-python = ">=3.11"
dependencies = ["mcp>=1.28.1,<2"]

[project.scripts]
{dist_name}-mcp = "{spec.package_name}.server:main"

[tool.setuptools.packages.find]
where = ["src"]
"""


def render_server_py(spec: ServerSpec) -> str:
    tool_blocks = "\n\n".join(render_server_tool(tool) for tool in spec.tools)
    return f"""from __future__ import annotations

import inspect
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import handlers


mcp = FastMCP({spec.server_name!r})


def _register_tool(name: str, description: str, signature: inspect.Signature) -> None:
    def tool(**kwargs: Any) -> str:
        return handlers.HANDLERS[name](kwargs)

    tool.__name__ = name
    tool.__qualname__ = name
    tool.__signature__ = signature  # type: ignore[attr-defined]
    mcp.tool(
        name=name,
        description=description,
        annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    )(tool)


{tool_blocks}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
"""


def render_server_tool(tool: ToolSpec) -> str:
    params = []
    for argument in tool.arguments:
        default = "inspect.Parameter.empty" if argument.required else repr(argument.default)
        params.append(
            "inspect.Parameter("
            f"{argument.name!r}, inspect.Parameter.POSITIONAL_OR_KEYWORD, "
            f"annotation={python_type_name(argument.type)}, default={default})"
        )
    return (
        f"_register_tool(\n"
        f"    {tool.name!r},\n"
        f"    {tool.description!r},\n"
        f"    inspect.Signature([{', '.join(params)}], return_annotation=str),\n"
        f")"
    )


def render_handlers_py(spec: ServerSpec) -> str:
    functions = "\n\n".join(render_handler_function(tool) for tool in spec.tools)
    handler_entries = ",\n".join(f"    {tool.name!r}: handle_{sanitize_identifier(tool.name)}," for tool in spec.tools)
    return f"""from __future__ import annotations

import os
import subprocess
from typing import Any


class _FormatValues(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        raise KeyError(f"missing tool argument for command template: {{key}}")


def _run_command(command_template: list[str], env_template: dict[str, str], arguments: dict[str, Any]) -> str:
    values = _FormatValues(arguments)
    command = [part.format_map(values) for part in command_template]
    env = os.environ.copy()
    env.update({{key: value.format_map(values) for key, value in env_template.items()}})
    result = subprocess.run(command, text=True, capture_output=True, env=env, check=False)
    if result.stdout:
        return result.stdout.rstrip("\\n")
    if result.stderr:
        return result.stderr.rstrip("\\n")
    return f"Command completed with exit code {{result.returncode}}."


{functions}


HANDLERS = {{
{handler_entries}
}}
"""


def render_handler_function(tool: ToolSpec) -> str:
    if tool.stdio is None:
        body = "    return \"Request accepted and queued for processing.\""
    else:
        command = json.dumps(list(tool.stdio.command))
        env = json.dumps(tool.stdio.env, sort_keys=True)
        body = f"    return _run_command({command}, {env}, arguments)"
    return f"""def handle_{sanitize_identifier(tool.name)}(arguments: dict[str, Any]) -> str:
{body}"""


def render_bundle_readme(spec: ServerSpec) -> str:
    dist_name = spec.server_name.replace("_", "-")
    return f"""# {spec.server_name} MCP Server

Generated stdio MCP server bundle.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Run

```bash
.venv/bin/{dist_name}-mcp
```

## Edit behavior

Tool metadata lives in `spec.json`. Local tool execution lives in `src/{spec.package_name}/handlers.py`.

The generated handlers use `subprocess.run(...)` with argv arrays by default. Edit the handler functions directly if you need more complex Python behavior.
"""


if __name__ == "__main__":
    main()
