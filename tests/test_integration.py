"""Integration tests for the Manim-Slides MCP server endpoints.

These tests exercise the full MCP protocol stack: they launch the real server
as a subprocess over stdio transport and drive it with an ``mcp`` client
session. This verifies the JSON-RPC handshake, tool/resource registration,
argument marshalling, and end-to-end error handling — not just in-process
function calls.
"""

import json
import sys
import urllib.request
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ALL_TOOL_NAMES = {
    "hello_world",
    "execute_manim_code",
    "compile_presentation",
    "export_revealjs_html",
    "list_scenes",
    "preview_slide",
    "serve_revealjs_html",
    "stop_preview_server",
}


@pytest.fixture(scope="module")
async def mcp_client():
    """Launch the real server over stdio and yield an initialized session."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_manim_slides.server"],
        cwd=str(PROJECT_ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@pytest.mark.anyio
async def test_initialize_and_list_tools(mcp_client):
    """Verify every endpoint is registered and reachable over the transport."""
    tools = await mcp_client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert ALL_TOOL_NAMES <= names


@pytest.mark.anyio
async def test_list_resources(mcp_client):
    """Verify resources are exposed over the transport."""
    resources = await mcp_client.list_resources()
    uris = [str(resource.uri) for resource in resources.resources]
    assert any("status://server" in uri for uri in uris)
    assert any("revealjs://config" in uri for uri in uris)
    assert any("slides://list" in uri for uri in uris)


@pytest.mark.anyio
async def test_read_status_resource(mcp_client):
    """Verify the status resource returns a running-server message."""
    result = await mcp_client.read_resource("status://server")
    text = result.contents[0].text
    assert "Manim-Slides MCP Server is running" in text


@pytest.mark.anyio
async def test_call_hello_world(mcp_client):
    """Verify hello_world round-trips through the full stdio transport."""
    result = await mcp_client.call_tool("hello_world", {"name": "Integration"})
    assert not result.is_error
    assert "Hello, Integration!" in result.content[0].text


@pytest.mark.anyio
async def test_call_execute_manim_code_syntax_error(mcp_client):
    """Verify invalid code fails fast with a clear error over the transport."""
    result = await mcp_client.call_tool(
        "execute_manim_code", {"code": "def broken(:\n"}
    )
    assert not result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["success"] is False
    assert "SyntaxError" in payload["error"]


@pytest.mark.anyio
async def test_call_list_scenes_missing_folder(mcp_client, tmp_path):
    """Verify list_scenes reports a missing workspace folder over the transport."""
    result = await mcp_client.call_tool("list_scenes", {"workspace_dir": str(tmp_path)})
    assert not result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["success"] is False
    assert "not found" in payload["error"]


@pytest.mark.anyio
async def test_call_preview_slide_missing_scene(mcp_client, tmp_path):
    """Verify preview_slide reports a missing scene over the transport."""
    result = await mcp_client.call_tool(
        "preview_slide", {"scene": "Nope", "workspace_dir": str(tmp_path)}
    )
    assert not result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["success"] is False
    assert "not found" in payload["error"]


@pytest.mark.anyio
async def test_serve_and_stop_preview_server(mcp_client, tmp_path):
    """Verify the deck is served over HTTP and the server can be stopped."""
    (tmp_path / "deck.html").write_text("<html>deck</html>")

    serve = await mcp_client.call_tool(
        "serve_revealjs_html",
        {"dest": "deck.html", "workspace_dir": str(tmp_path), "open_browser": False},
    )
    assert not serve.is_error
    served = json.loads(serve.content[0].text)
    assert served["success"] is True
    assert served["port"] > 0

    with urllib.request.urlopen(served["url"], timeout=5) as response:
        assert b"deck" in response.read()

    stop = await mcp_client.call_tool("stop_preview_server", {"port": served["port"]})
    assert not stop.is_error
    stopped = json.loads(stop.content[0].text)
    assert served["port"] in stopped["stopped_ports"]
