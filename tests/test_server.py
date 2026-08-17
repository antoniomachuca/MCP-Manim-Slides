"""Unit tests for Manim-Slides MCP Server."""

import json
import subprocess
from pathlib import Path

import pytest

from src.server import (
    _build_convert_command,
    _build_render_command,
    _temporary_script,
    compile_presentation,
    execute_manim_code,
    hello_world,
    mcp,
    server_status,
)


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


def test_build_convert_command_defaults():
    """Verify default arguments produce a minimal manim-slides convert command."""
    command = _build_convert_command(scenes=["MySlide"], dest="out.html")
    args = command[command.index("convert") :]
    assert args == [
        "convert",
        "--folder",
        "slides",
        "--to",
        "auto",
        "MySlide",
        "out.html",
    ]


def test_build_convert_command_full_options():
    """Verify all optional flags and config options are forwarded correctly."""
    command = _build_convert_command(
        scenes=["SceneA", "SceneB"],
        dest="deck.html",
        folder="media",
        output_format="html",
        config={"slide_number": "true"},
        one_file=True,
    )
    args = command[command.index("convert") :]
    assert args == [
        "convert",
        "--folder",
        "media",
        "--to",
        "html",
        "--one-file",
        "-c",
        "slide_number=true",
        "SceneA",
        "SceneB",
        "deck.html",
    ]


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_compile_presentation_success(monkeypatch):
    """Verify compile_presentation returns a successful structured response."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(0, stdout="Done"),
    )
    result = json.loads(compile_presentation(scenes=["MySlide"], dest="out.html"))
    assert result["success"] is True
    assert result["scenes"] == ["MySlide"]
    assert result["destination"].endswith("out.html")


def test_compile_presentation_failure(monkeypatch):
    """Verify compile_presentation surfaces the converter error on failure."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(1, stderr="Slide not found"),
    )
    result = json.loads(compile_presentation(scenes=["MissingSlide"], dest="out.html"))
    assert result["success"] is False
    assert "Slide not found" in result["error"]


@pytest.mark.anyio
async def test_server_list_tools_includes_compile_presentation():
    """Verify compile_presentation tool is registered on the MCPServer."""
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "compile_presentation" in tool_names

    compile_tool = next(t for t in tools if t.name == "compile_presentation")
    assert "manim-slides convert" in compile_tool.description
    assert "scenes" in compile_tool.input_schema["properties"]
    assert "dest" in compile_tool.input_schema["properties"]


def test_build_render_command_with_scenes():
    """Verify render command includes quality, media dir, script, and scenes."""
    command = _build_render_command(
        script=Path("script.py"),
        scenes=["MySlide"],
        quality="l",
        media_dir=Path("/tmp/media"),
    )
    args = command[command.index("render") :]
    assert args == [
        "render",
        "-q",
        "l",
        "--media_dir",
        "/tmp/media",
        "script.py",
        "MySlide",
    ]


def test_build_render_command_write_all():
    """Verify render command uses -a when no scenes are provided."""
    command = _build_render_command(
        script=Path("script.py"),
        scenes=[],
        quality="m",
        media_dir=Path("/tmp/media"),
    )
    args = command[command.index("render") :]
    assert args == [
        "render",
        "-q",
        "m",
        "--media_dir",
        "/tmp/media",
        "-a",
        "script.py",
    ]


def test_temporary_script_creation_and_cleanup(tmp_path):
    """Verify the temporary script is written and removed after the context."""
    with _temporary_script("print('hi')", tmp_path) as script:
        assert script.exists()
        assert script.read_text() == "print('hi')"
        assert script.name.endswith(".py")
    assert not script.exists()


def test_execute_manim_code_success(monkeypatch, tmp_path):
    """Verify execute_manim_code returns a successful structured response."""

    def fake_run(command, **kwargs):
        media_dir = Path(command[command.index("--media_dir") + 1])
        video = media_dir / "videos" / "480p15" / "MySlide.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_text("fake")
        return _FakeCompletedProcess(0, stdout="Rendered")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = json.loads(
        execute_manim_code(
            code="from manim_slides import Slide\nclass MySlide(Slide): pass\n",
            scenes=["MySlide"],
            media_dir=str(tmp_path),
        )
    )
    assert result["success"] is True
    assert result["scenes"] == ["MySlide"]
    assert any(f.endswith("MySlide.mp4") for f in result["media_files"])


def test_execute_manim_code_failure(monkeypatch, tmp_path):
    """Verify execute_manim_code surfaces the render error on failure."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(1, stderr="SyntaxError"),
    )
    result = json.loads(
        execute_manim_code(code="invalid python", media_dir=str(tmp_path))
    )
    assert result["success"] is False
    assert "SyntaxError" in result["error"]


@pytest.mark.anyio
async def test_server_list_tools_includes_execute_manim_code():
    """Verify execute_manim_code tool is registered on the MCPServer."""
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "execute_manim_code" in tool_names

    exec_tool = next(t for t in tools if t.name == "execute_manim_code")
    assert "manim-slides render" in exec_tool.description
    assert "code" in exec_tool.input_schema["properties"]
    assert "scenes" in exec_tool.input_schema["properties"]
