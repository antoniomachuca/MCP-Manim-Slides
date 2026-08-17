"""Unit tests for Manim-Slides MCP Server."""

import json
import subprocess
from pathlib import Path

import pytest

from src.server import (
    REVEAL_THEMES,
    REVEAL_TRANSITION_SPEEDS,
    REVEAL_TRANSITIONS,
    _build_convert_command,
    _build_render_command,
    _build_reveal_config,
    _build_revealjs_export_command,
    _temporary_script,
    _validate_reveal_options,
    compile_presentation,
    execute_manim_code,
    export_revealjs_html,
    hello_world,
    list_scenes,
    mcp,
    preview_slide,
    revealjs_config_options,
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
    assert any("revealjs://config" in uri for uri in resource_uris)


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


def test_build_reveal_config_defaults():
    """Verify default Reveal.js config produces expected -c key=value pairs."""
    args = _build_reveal_config()
    assert args == [
        "-c",
        "reveal_theme=black",
        "-c",
        "transition='none'",
        "-c",
        "transition_speed='default'",
        "-c",
        "controls=false",
        "-c",
        "progress=false",
        "-c",
        "slide_number=false",
        "-c",
        "hash=false",
        "-c",
        "loop=false",
    ]


def test_build_reveal_config_full_options():
    """Verify custom Reveal.js options are converted to converter arguments."""
    args = _build_reveal_config(
        theme="moon",
        transition="slide",
        transition_speed="fast",
        controls=True,
        progress=True,
        slide_number=True,
        hash=True,
        loop=True,
        title="My Deck",
        config={"background_color": "white"},
    )
    assert args.count("-c") == 10
    assert "reveal_theme=moon" in args
    assert "transition='slide'" in args
    assert "transition_speed='fast'" in args
    assert "controls=true" in args
    assert "progress=true" in args
    assert "slide_number=true" in args
    assert "hash=true" in args
    assert "loop=true" in args
    assert "title=My Deck" in args
    assert "background_color=white" in args


def test_build_revealjs_export_command_defaults():
    """Verify Reveal.js export builds a convert command targeting html."""
    command = _build_revealjs_export_command(scenes=["MySlide"], dest="deck.html")
    args = command[command.index("convert") :]
    assert args[0] == "convert"
    assert args[1:5] == ["--folder", "slides", "--to", "html"]
    assert "MySlide" in args
    assert args[-1] == "deck.html"


def test_build_revealjs_export_command_full_options():
    """Verify all Reveal.js flags (one-file, offline) are forwarded correctly."""
    command = _build_revealjs_export_command(
        scenes=["SceneA", "SceneB"],
        dest="deck.html",
        folder="media",
        theme="sky",
        transition="fade",
        one_file=True,
        offline=True,
    )
    args = command[command.index("convert") :]
    assert args[1:5] == ["--folder", "media", "--to", "html"]
    assert "--one-file" in args
    assert "--offline" in args
    assert "reveal_theme=sky" in args
    assert "transition='fade'" in args
    assert args[-3:] == ["SceneA", "SceneB", "deck.html"]


def test_validate_reveal_options_valid():
    """Verify valid theme, transition, and speed produce no error."""
    assert _validate_reveal_options("moon", "slide", "fast") is None


def test_validate_reveal_options_invalid_theme():
    """Verify an invalid theme returns a descriptive error message."""
    error = _validate_reveal_options("rainbow", "none", "default")
    assert error is not None
    assert "rainbow" in error
    assert "theme" in error


def test_validate_reveal_options_invalid_transition():
    """Verify an invalid transition returns a descriptive error message."""
    error = _validate_reveal_options("black", "explode", "default")
    assert error is not None
    assert "explode" in error
    assert "transition" in error


def test_validate_reveal_options_invalid_speed():
    """Verify an invalid transition speed returns a descriptive error message."""
    error = _validate_reveal_options("black", "none", "ludicrous")
    assert error is not None
    assert "ludicrous" in error
    assert "speed" in error


def test_export_revealjs_html_invalid_theme(monkeypatch):
    """Verify invalid theme is rejected before invoking the converter."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(0, stdout="Done"),
    )
    result = json.loads(
        export_revealjs_html(scenes=["MySlide"], dest="deck.html", theme="rainbow")
    )
    assert result["success"] is False
    assert "rainbow" in result["error"]


def test_revealjs_config_options_resource():
    """Verify the revealjs config resource lists supported options."""
    config = json.loads(revealjs_config_options())
    assert config["themes"] == list(REVEAL_THEMES)
    assert config["transitions"] == list(REVEAL_TRANSITIONS)
    assert config["transition_speeds"] == list(REVEAL_TRANSITION_SPEEDS)
    assert "controls" in config["boolean_options"]
    assert config["defaults"]["theme"] == "black"


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


def test_export_revealjs_html_success(monkeypatch):
    """Verify export_revealjs_html returns a successful structured response."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(0, stdout="Done"),
    )
    result = json.loads(export_revealjs_html(scenes=["MySlide"], dest="deck.html"))
    assert result["success"] is True
    assert result["format"] == "html"
    assert result["scenes"] == ["MySlide"]
    assert result["destination"].endswith("deck.html")


def test_export_revealjs_html_failure(monkeypatch):
    """Verify export_revealjs_html surfaces the converter error on failure."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(1, stderr="Slide not found"),
    )
    result = json.loads(
        export_revealjs_html(scenes=["MissingSlide"], dest="deck.html")
    )
    assert result["success"] is False
    assert "Slide not found" in result["error"]


@pytest.mark.anyio
async def test_server_list_tools_includes_export_revealjs_html():
    """Verify export_revealjs_html tool is registered on the MCPServer."""
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "export_revealjs_html" in tool_names

    export_tool = next(t for t in tools if t.name == "export_revealjs_html")
    assert "Reveal.js" in export_tool.description
    assert "scenes" in export_tool.input_schema["properties"]
    assert "theme" in export_tool.input_schema["properties"]


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


def _write_scene_config(tmp_path: Path, scene: str, slides: list[dict]) -> Path:
    """Create a fake slides folder with a scene config and media files."""
    slides_dir = tmp_path / "slides"
    slides_dir.mkdir(exist_ok=True)
    for slide in slides:
        file = slide["file"]
        media_path = tmp_path / file
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text("fake")
    (slides_dir / f"{scene}.json").write_text(
        json.dumps(
            {
                "slides": slides,
                "resolution": [854, 480],
                "background_color": "black",
            }
        )
    )
    return slides_dir


def test_list_scenes_success(tmp_path):
    """Verify list_scenes discovers scenes and their slide metadata."""
    _write_scene_config(
        tmp_path,
        "MySlide",
        [
            {"type": "video", "file": "slides/files/MySlide/0.mp4"},
            {"type": "video", "file": "slides/files/MySlide/1.mp4"},
        ],
    )
    result = json.loads(list_scenes(workspace_dir=str(tmp_path)))
    assert result["success"] is True
    assert result["scene_count"] == 1
    assert result["scenes"][0]["scene"] == "MySlide"
    assert result["scenes"][0]["slide_count"] == 2
    assert result["scenes"][0]["resolution"] == [854, 480]
    assert result["scenes"][0]["slides"][0]["type"] == "video"


def test_list_scenes_missing_folder(tmp_path):
    """Verify list_scenes reports an error when the folder is absent."""
    result = json.loads(list_scenes(workspace_dir=str(tmp_path)))
    assert result["success"] is False
    assert "not found" in result["error"]


def test_preview_slide_video_to_png(monkeypatch, tmp_path):
    """Verify preview_slide extracts a PNG frame from a video slide."""
    _write_scene_config(
        tmp_path,
        "MySlide",
        [{"type": "video", "file": "slides/files/MySlide/0.mp4"}],
    )

    def fake_run(command, **kwargs):
        destination = Path(command[-1])
        destination.write_text("fake-png")
        return _FakeCompletedProcess(0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("src.server._ffmpeg_executable", lambda: "/usr/bin/ffmpeg")

    result = json.loads(
        preview_slide(scene="MySlide", workspace_dir=str(tmp_path))
    )
    assert result["success"] is True
    assert result["scene"] == "MySlide"
    assert result["slide_index"] == 0
    assert result["output_format"] == "png"
    assert result["preview_path"].endswith("MySlide_0.png")


def test_preview_slide_video_to_mp4_copy(monkeypatch, tmp_path):
    """Verify preview_slide copies the slide video for mp4 output."""
    _write_scene_config(
        tmp_path,
        "MySlide",
        [{"type": "video", "file": "slides/files/MySlide/0.mp4"}],
    )
    result = json.loads(
        preview_slide(
            scene="MySlide",
            slide_index=0,
            output_format="mp4",
            workspace_dir=str(tmp_path),
        )
    )
    assert result["success"] is True
    assert result["preview_path"].endswith("MySlide_0.mp4")


def test_preview_slide_out_of_range(tmp_path):
    """Verify preview_slide reports an error for an invalid slide index."""
    _write_scene_config(
        tmp_path,
        "MySlide",
        [{"type": "video", "file": "slides/files/MySlide/0.mp4"}],
    )
    result = json.loads(
        preview_slide(scene="MySlide", slide_index=5, workspace_dir=str(tmp_path))
    )
    assert result["success"] is False
    assert "out of range" in result["error"]


def test_preview_slide_missing_scene(tmp_path):
    """Verify preview_slide reports an error when the scene is not found."""
    result = json.loads(
        preview_slide(scene="Nope", workspace_dir=str(tmp_path))
    )
    assert result["success"] is False
    assert "not found" in result["error"]


def test_preview_slide_unsupported_format(tmp_path):
    """Verify preview_slide rejects unsupported output formats."""
    _write_scene_config(
        tmp_path,
        "MySlide",
        [{"type": "video", "file": "slides/files/MySlide/0.mp4"}],
    )
    result = json.loads(
        preview_slide(scene="MySlide", output_format="pdf", workspace_dir=str(tmp_path))
    )
    assert result["success"] is False
    assert "Unsupported output_format" in result["error"]


@pytest.mark.anyio
async def test_server_list_tools_includes_preview_and_list_scenes():
    """Verify list_scenes and preview_slide tools are registered."""
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "list_scenes" in tool_names
    assert "preview_slide" in tool_names

    preview_tool = next(t for t in tools if t.name == "preview_slide")
    assert "scene" in preview_tool.input_schema["properties"]
    assert "output_format" in preview_tool.input_schema["properties"]
