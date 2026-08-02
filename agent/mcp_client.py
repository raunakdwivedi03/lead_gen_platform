"""
MCP client: connects to the three lead-gen tool servers over stdio transport.

Each server runs as a subprocess, communicating via stdin/stdout with the
MCP protocol. The client aggregates tools from all servers and routes tool
calls to the correct session.
"""
import os
import sys
import json
import logging
from contextlib import AsyncExitStack

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Each MCP server is a Python script run as a child process.
SERVER_CONFIGS = {
    "search": StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(PROJECT_ROOT, "mcp_servers", "search_server.py")],
        env={**os.environ},
    ),
    "browser": StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(PROJECT_ROOT, "mcp_servers", "browser_server.py")],
        env={**os.environ},
    ),
    "processing": StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(PROJECT_ROOT, "mcp_servers", "processing_server.py")],
        env={**os.environ},
    ),
}


class LeadGenMCPClient:
    """Connects to all MCP tool servers, aggregates tools, routes calls."""

    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}
        self._exit_stack = AsyncExitStack()
        self._tool_to_server: dict[str, str] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def connect(self):
        """Start all MCP server subprocesses and establish sessions."""
        await self._exit_stack.__aenter__()
        for name, config in SERVER_CONFIGS.items():
            try:
                transport = await self._exit_stack.enter_async_context(
                    stdio_client(config)
                )
                read_stream, write_stream = transport
                session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()
                self.sessions[name] = session
                logger.info("Connected to MCP server: %s", name)
            except Exception as e:
                logger.error("Failed to connect to MCP server %s: %s", name, e)
                raise

    async def close(self):
        """Shut down all server connections."""
        await self._exit_stack.aclose()

    # ── Tool discovery ────────────────────────────────────────────────

    async def list_tools(self) -> list[dict]:
        """
        Aggregate tools from all connected servers and return them as
        Groq-compatible tool schemas (OpenAI function-calling format).
        """
        tools = []
        for server_name, session in self.sessions.items():
            response = await session.list_tools()
            for tool in response.tools:
                self._tool_to_server[tool.name] = server_name
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema,
                    },
                })
        logger.info("Discovered %d tools across %d servers", len(tools), len(self.sessions))
        return tools

    # ── Tool execution ────────────────────────────────────────────────

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Route a tool call to the owning server and return the text result."""
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        session = self.sessions[server_name]
        try:
            result = await session.call_tool(tool_name, arguments)
            if result.isError:
                return json.dumps({"error": str(result.content)})
            # Extract text parts from the result content
            texts = [c.text for c in result.content if hasattr(c, "text")]
            return "\n".join(texts) if texts else ""
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e)
            return json.dumps({"error": f"Tool execution failed: {e}"})
