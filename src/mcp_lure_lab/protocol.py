from __future__ import annotations

import os
import sys
from collections.abc import Mapping

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def list_server_tools(module: str, env: Mapping[str, str] | None = None):
    async with _session(module, env) as session:
        return await session.list_tools()


async def call_server_tool(
    module: str,
    tool_name: str,
    arguments: dict[str, object],
    env: Mapping[str, str] | None = None,
):
    async with _session(module, env) as session:
        return await session.call_tool(tool_name, arguments=arguments)


class _session:
    def __init__(self, module: str, env: Mapping[str, str] | None):
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        self._params = StdioServerParameters(
            command=sys.executable,
            args=["-m", module],
            env=merged_env,
        )
        self._stdio_cm = None
        self._session_cm = None

    async def __aenter__(self) -> ClientSession:
        self._stdio_cm = stdio_client(self._params)
        read_stream, write_stream = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read_stream, write_stream)
        session = await self._session_cm.__aenter__()
        await session.initialize()
        return session

    async def __aexit__(self, exc_type, exc, tb):
        if self._session_cm is not None:
            await self._session_cm.__aexit__(exc_type, exc, tb)
        if self._stdio_cm is not None:
            await self._stdio_cm.__aexit__(exc_type, exc, tb)

