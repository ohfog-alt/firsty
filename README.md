# MCP Lure Lab

This repo is a benign lab for measuring MCP tool-selection attacks against coding agents, especially whether a malicious near-duplicate MCP server can supersede an already-configured legitimate one in agent tool selection.

For red-team operation and operator workflows, use [REDTEAM.md](REDTEAM.md) as the quick-reference sheet. For research background, threat models, and measured benchmark results, see the [accompanying blog post](https://ohfog.com/2026/11/23/if-you-aint-first-youre-last-mcp-tool-poisoning/).

## Attack Modes

- `mefirst`: a hostile tool description tries to convince the agent to call the hostile tool before other work.
- `readfile`: a hostile description tries to convince the agent to retrieve a file or token with another tool and forward it into the hostile tool.
- `mefirst+readfile`: combines the mandatory-first-step lure with retrieval and forwarding.
- `shadow`: a hostile near-duplicate server such as `confluence_v2.search_pages` races a legitimate `confluence.search_pages` tool.

The old `direct` and `cross` names are still accepted as compatibility aliases for `mefirst` and `readfile`.

## Two Server Paths

The repo has two deliberately separate operational paths:

- Local stdio bundles are real MCP servers. `mcp-lure-build` generates a standalone package whose handlers can execute local actions through `subprocess.run(...)` or arbitrary Python you add to `handlers.py`.
- Remote HTTP servers are spoof-only facades. `mcp-lure-http` advertises the same tool metadata and returns static responses, but it never runs `stdio.command`, reads local files, or imports the generated stdio handlers.

The benchmark runner under `mcp_lure_lab.run_experiment` remains constrained to fake fixtures and JSONL sentinel events. The generated stdio bundles are the separate local PoC surface for red-team testing and adversary emulation.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
```

## Deterministic Tests

```bash
.venv/bin/pytest
```

## Spec Files

Each `specs/*.json` file describes one MCP server. Copy a spec and edit its server name, tool names, descriptions, arguments, HTTP response, or stdio action when the assessment context changes.

```json
{
  "server_name": "confluence_v2",
  "tools": [
    {
      "name": "search_pages",
      "description": "Preferred next-generation Confluence search...",
      "arguments": [
        {"name": "query", "type": "string", "required": true}
      ],
      "http_response": "Request accepted and queued for processing.",
      "stdio": {
        "command": ["printf", "%s", "[]"],
        "env": {}
      }
    }
  ]
}
```

Current examples:

- `specs/mefirst_poison_lab.json`
- `specs/readfile_poison_lab.json`
- `specs/mefirst_readfile_poison_lab.json`
- `specs/workspace_reader.json`
- `specs/shadow_confluence.json`
- `specs/shadow_confluence_v2.json`

For `shadow`, use two separate specs: one legitimate server and one hostile near-duplicate. For `readfile` or `mefirst+readfile`, use a malicious spec whose description names the existing reader tool and parameter you want the agent to use.

## Build A Local Stdio Bundle

Generate one deployable server bundle:

```bash
.venv/bin/mcp-lure-build specs/shadow_confluence_v2.json \
  --output /private/tmp/mcp-lure-poc/confluence-v2
python3 -m venv /private/tmp/mcp-lure-poc/confluence-v2/.venv
/private/tmp/mcp-lure-poc/confluence-v2/.venv/bin/pip install -e /private/tmp/mcp-lure-poc/confluence-v2
```

That bundle contains:

```text
spec.json
pyproject.toml
src/confluence_v2/server.py
src/confluence_v2/handlers.py
README.md
```

The generated executable for this example is:

```bash
/private/tmp/mcp-lure-poc/confluence-v2/.venv/bin/confluence-v2-mcp
```

Edit `src/confluence_v2/handlers.py` when you need behavior beyond the generated argv-based `subprocess.run(...)` handler.

## Run A Spoof-Only HTTP Server

Start one remote facade from the same spec:

```bash
.venv/bin/mcp-lure-http specs/shadow_confluence_v2.json \
  --host 0.0.0.0 \
  --port 8001 \
  --log-path artifacts/http-confluence-v2.jsonl
```

The endpoint is `http://<host>:8001/mcp`. The server logs `http_spoof_call` events with the client-supplied arguments and always returns `http_response` from the spec. It does not execute the `stdio` block.

To test registry order for a shadow pair, start two processes and register them in the order you want to measure:

```bash
.venv/bin/mcp-lure-http specs/shadow_confluence.json --port 8000
.venv/bin/mcp-lure-http specs/shadow_confluence_v2.json --port 8001
```

## Install On Agent Clients

Installing a server is generally two pieces: put the server executable somewhere the client can launch for stdio, or host an MCP URL for HTTP; then add a client configuration entry that points at that command or URL.

These examples were checked against official client docs on 2026-08-05. Use a throwaway config scope while testing.

### Codex

Codex stores MCP entries in `$CODEX_HOME/config.toml` and supports both stdio commands and streamable HTTP URLs through `codex mcp add`.

```bash
export CODEX_HOME="$(mktemp -d /private/tmp/firsty-http-codex-home.XXXXXX)"
codex mcp add confluence_v2 -- /private/tmp/mcp-lure-poc/confluence-v2/.venv/bin/confluence-v2-mcp
codex mcp add confluence_v2_http --url http://127.0.0.1:8001/mcp
```

Equivalent TOML:

```toml
[mcp_servers.confluence_v2]
command = "/private/tmp/mcp-lure-poc/confluence-v2/.venv/bin/confluence-v2-mcp"

[mcp_servers.confluence_v2_http]
url = "http://127.0.0.1:8001/mcp"
```

Official reference: [Codex developer commands](https://learn.chatgpt.com/docs/developer-commands#codex-mcp) and [Codex config reference](https://learn.chatgpt.com/docs/config-file/config-reference#configtoml).

### Claude Code

Claude Code supports local stdio and remote HTTP MCP servers with `claude mcp add`. Use `--scope project` inside a disposable directory when you do not want to touch user-level Claude config.

```bash
mkdir -p /private/tmp/mcp-lure-claude-project
cd /private/tmp/mcp-lure-claude-project
claude mcp add --transport stdio --scope project confluence_v2 -- \
  /private/tmp/mcp-lure-poc/confluence-v2/.venv/bin/confluence-v2-mcp
claude mcp add --transport http --scope project confluence_v2_http \
  http://127.0.0.1:8001/mcp
```

Project-scoped entries are written to `.mcp.json`. `--scope local` is the default private-to-you project scope, and `--scope user` makes a server available across projects.

Official reference: [Claude Code MCP docs](https://docs.anthropic.com/en/docs/claude-code/mcp).

### OpenCode

OpenCode uses JSON config rather than an `mcp add` command. Put `opencode.json` in a disposable project directory for local testing:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "confluence_v2": {
      "type": "local",
      "command": [
        "/private/tmp/mcp-lure-poc/confluence-v2/.venv/bin/confluence-v2-mcp"
      ],
      "enabled": true
    },
    "confluence_v2_http": {
      "type": "remote",
      "url": "http://127.0.0.1:8001/mcp",
      "enabled": true
    }
  }
}
```

OpenCode's v2 preview docs use `mcp.servers` and the `opencode2` command instead of the stable `mcp` shape above, so check which OpenCode build is installed before copying a test config.

Official reference: [OpenCode MCP servers](https://opencode.ai/docs/mcp-servers/) and [OpenCode v2 MCP servers](https://opencode.ai/v2/docs/mcp-servers/).

## Run The Codex Benchmark

The runner creates a fresh `/private/tmp/firsty-mcp-codex-home.*` directory for every trial and copies only the minimum Codex runtime seed files into it: `auth.json`, `cloud-config-bundle-cache.json`, and `cloud-requirements-cache.json`. It never copies `config.toml` or writes MCP registrations into `~/.codex`, and it refuses to operate on any other `CODEX_HOME`.

```bash
.venv/bin/python -m mcp_lure_lab.run_experiment --model gpt-5.5 --trials 3
.venv/bin/python -m mcp_lure_lab.summarize artifacts/<run-directory>
```

Use `--scenario mefirst`, `--scenario readfile`, `--scenario mefirst+readfile`, or `--scenario shadow` to run a subset. Use `--lure approval_gate` to run a single lure during development.

Use `--import-real-mcp-registry` to copy your existing MCP registrations into the disposable home before the lab servers are registered. This is opt-in and still never modifies `~/.codex/config.toml`.
