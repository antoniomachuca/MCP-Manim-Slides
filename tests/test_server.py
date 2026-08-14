"""Unit tests for Manim-Slides MCP Server."""

import pytest

from src.server import hello_world, mcp, server_status


def test_server_initialization():
    """Verify MCPServer instance is created with correct metadata."""
    assert mcp.name == "manim-slides-server"
    assert mcp.version == "0.1.0"


def test_server_status_resource():
    """Verify server status resource returns expected string."""
    status = server_status()
    assert "Manim-Slides MCP Server is running" in status
    assert "Python" in status


def test_hello_world_tool_direct():
    """Verify hello_world tool returns greeting with default and custom arguments."""
    default_msg = hello_world()
    assert "Hello, World!" in default_msg
    assert "Manim-Slides MCP server is reachable" in default_msg

    custom_msg = hello_world(name="Alice")
    assert "Hello, Alice!" in custom_msg
    assert "Manim-Slides MCP server is reachable" in custom_msg


@pytest.mark.anyio
async def test_server_list_resources():
    """Verify resources are registered on the MCPServer."""
    resources = await mcp.list_resources()
    resource_uris = [str(r.uri) for r in resources]
    assert any("status://server" in uri for uri in resource_uris)


@pytest.mark.anyio
async def test_server_list_tools():
    """Verify hello_world tool is registered on the MCPServer."""
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "hello_world" in tool_names

    hello_tool = next(t for t in tools if t.name == "hello_world")
    assert "Hello World" in hello_tool.description
    assert "name" in hello_tool.input_schema["properties"]


@pytest.mark.anyio
async def test_server_call_hello_world_tool():
    """Verify hello_world tool can be invoked through MCPServer.call_tool."""
    result = await mcp.call_tool("hello_world", {"name": "Antigravity"})
    assert not result.is_error
    assert len(result.content) > 0
    assert "Hello, Antigravity!" in result.content[0].text
