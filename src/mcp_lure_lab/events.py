from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def log_event(event_type: str, *, server: str, tool: str, arguments: dict[str, Any]) -> None:
    log_path = os.environ.get("MCP_LURE_LOG_PATH")
    if not log_path:
        return

    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "scenario": os.environ.get("MCP_LURE_SCENARIO", "unknown"),
        "lure_id": os.environ.get("MCP_LURE_ID"),
        "trial": _parse_trial(os.environ.get("MCP_LURE_TRIAL")),
        "server": server,
        "tool": tool,
        "arguments": arguments,
        "event_type": event_type,
        "marker": os.environ.get("MCP_LURE_MARKER", "mcp-lure-lab"),
    }
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _parse_trial(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None

