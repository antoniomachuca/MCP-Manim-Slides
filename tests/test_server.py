"""Unit tests for Manim-Slides MCP Server."""

import asyncio
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from mcp_manim_slides.server import (
    REVEAL_THEMES,
    REVEAL_TRANSITION_SPEEDS,
    REVEAL_TRANSITIONS,
    RenderProgress,
    _build_convert_command,
    _build_export_command,
    _build_render_command,
    _build_reveal_config,
    _build_revealjs_export_command,
    _concat_list_text,
    _extract_missing_module,
    _extract_scene_fragments,
    _ffprobe_duration,
    _format_progress_message,
    _load_render_cache,
    _manim_slides_availability_error,
    _parse_render_progress,
    _render_cache_key,
    _restore_render_cache,
    _run_render_streaming,
    _save_render_cache,
    _scene_cache_key,
    _temporary_script,
    _validate_python_syntax,
    _validate_reveal_options,
    compile_presentation,
    execute_manim_code,
    export_revealjs_html,
    export_video,
    hello_world,
    list_scenes,
    mcp,
    preview_slide,
    revealjs_config_options,
    serve_revealjs_html,
    server_status,
    slides_list,
    stop_preview_server,
    sync_deck,
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
    assert any("slides://list" in uri for uri in resource_uris)


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
    result = json.loads(export_revealjs_html(scenes=["MissingSlide"], dest="deck.html"))
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


class _FakeStreamReader:
    """Minimal async stream reader that drains a fixed byte payload."""

    def __init__(self, data: bytes):
        self._data = data

    async def read(self, n: int = -1) -> bytes:
        if n == -1 or n > len(self._data):
            n = len(self._data)
        out = self._data[:n]
        self._data = self._data[n:]
        return out


class _FakeAsyncProcess:
    """Minimal stand-in for ``asyncio.subprocess.Process``."""

    def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
        self._returncode = returncode
        self.stdout = _FakeStreamReader(stdout)
        self.stderr = _FakeStreamReader(stderr)
        self.killed = False

    async def wait(self) -> int:
        return self._returncode

    def kill(self) -> None:
        self.killed = True
        self._returncode = -9


class _RecordingContext:
    """A Context stand-in that records ``report_progress`` calls."""

    def __init__(self):
        self.reports: list[tuple[float, float | None, str | None]] = []

    async def report_progress(
        self, progress: float, total: float | None = None, message: str | None = None
    ) -> None:
        self.reports.append((progress, total, message))


def _patch_async_exec(monkeypatch, process):
    """Patch ``asyncio.create_subprocess_exec`` to return ``process``."""

    async def fake_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)


@pytest.mark.anyio
async def test_execute_manim_code_success(monkeypatch, tmp_path):
    """Verify execute_manim_code returns a successful structured response."""

    async def fake_exec(*args, **kwargs):
        media_dir = Path(kwargs["cwd"])
        video = media_dir / "videos" / "480p15" / "MySlide.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_text("fake")
        return _FakeAsyncProcess(0, stdout=b"Rendered")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    result = json.loads(
        await execute_manim_code(
            code="from manim_slides import Slide\nclass MySlide(Slide): pass\n",
            scenes=["MySlide"],
            media_dir=str(tmp_path),
        )
    )
    assert result["success"] is True
    assert result["scenes"] == ["MySlide"]
    assert any(f.endswith("MySlide.mp4") for f in result["media_files"])


@pytest.mark.anyio
async def test_execute_manim_code_failure(monkeypatch, tmp_path):
    """Verify execute_manim_code surfaces the render error on failure."""
    _patch_async_exec(
        monkeypatch,
        _FakeAsyncProcess(1, stderr=b"RuntimeError: something went wrong"),
    )
    result = json.loads(
        await execute_manim_code(
            code="raise RuntimeError('something went wrong')\n",
            media_dir=str(tmp_path),
        )
    )
    assert result["success"] is False
    assert "RuntimeError" in result["error"]


@pytest.mark.anyio
async def test_execute_manim_code_syntax_error_no_subprocess(monkeypatch, tmp_path):
    """Verify invalid code is rejected before any subprocess is spawned."""
    calls: list[tuple] = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        return _FakeAsyncProcess(0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    result = json.loads(
        await execute_manim_code(code="def broken(:\n", media_dir=str(tmp_path))
    )
    assert result["success"] is False
    assert "SyntaxError" in result["error"]
    assert calls == []


@pytest.mark.anyio
async def test_execute_manim_code_missing_dependency(monkeypatch, tmp_path):
    """Verify missing imports are surfaced with an actionable hint."""
    _patch_async_exec(
        monkeypatch,
        _FakeAsyncProcess(
            1,
            stderr=(
                b"Traceback (most recent call last):\n"
                b"ModuleNotFoundError: No module named 'numpy'\n"
            ),
        ),
    )
    result = json.loads(
        await execute_manim_code(
            code="import numpy as np\nclass MySlide(Slide): pass\n",
            media_dir=str(tmp_path),
        )
    )
    assert result["success"] is False
    assert result["missing_dependency"] == "numpy"
    assert "pip install numpy" in result["hint"]


def test_validate_python_syntax_valid():
    """Verify valid Python code passes syntax validation."""
    assert _validate_python_syntax("class MySlide(Slide): pass\n") is None


def test_validate_python_syntax_invalid():
    """Verify invalid Python code returns a precise, line-aware error."""
    error = _validate_python_syntax("def broken(:\n    pass\n")
    assert error is not None
    assert "SyntaxError" in error
    assert "line 1" in error


def test_extract_missing_module_detects_import_error():
    """Verify missing module names are parsed from stderr tracebacks."""
    stderr = "ModuleNotFoundError: No module named 'requests'"
    assert _extract_missing_module(stderr) == "requests"


def test_extract_missing_module_no_match():
    """Verify unrelated stderr returns None."""
    assert _extract_missing_module("Some other error") is None


def test_manim_slides_availability_error_resolves(monkeypatch):
    """Verify availability check passes when the module is importable."""
    monkeypatch.setattr("mcp_manim_slides.server.shutil.which", lambda _name: None)
    monkeypatch.setattr("mcp_manim_slides.server._module_available", lambda _name: True)
    assert _manim_slides_availability_error() is None


def test_manim_slides_availability_error_reports(monkeypatch):
    """Verify availability check reports a clear error when manim-slides is absent."""
    monkeypatch.setattr("mcp_manim_slides.server.shutil.which", lambda _name: None)
    monkeypatch.setattr(
        "mcp_manim_slides.server._module_available", lambda _name: False
    )
    error = _manim_slides_availability_error()
    assert error is not None
    assert "manim-slides is not installed" in error


@pytest.mark.anyio
async def test_run_render_streaming_timeout_kills_process(tmp_path):
    """Verify a runaway render is killed and raises TimeoutExpired."""
    command = [sys.executable, "-c", "import time; time.sleep(60)"]
    with pytest.raises(subprocess.TimeoutExpired):
        await _run_render_streaming(
            command=command,
            workspace=tmp_path,
            scenes=["Hang"],
            quality="l",
            start=time.time(),
            timeout=1,
            ctx=None,
        )


@pytest.mark.anyio
async def test_execute_manim_code_streams_progress(monkeypatch, tmp_path):
    """Verify render frame percentages are streamed as progress notifications."""
    stderr = (
        "\rAnimation 0: FadeIn(Circle):   0%|          | 0/2 [00:00<?, ?it/s]"
        "\rAnimation 0: FadeIn(Circle):  50%|█████     | 1/2 [00:01<00:01, 1.00it/s]"
        "\rAnimation 0: FadeIn(Circle): 100%|██████████| 2/2 [00:02<00:00, 1.00it/s]\n"
    ).encode()
    _patch_async_exec(
        monkeypatch,
        _FakeAsyncProcess(0, stdout=b"Rendered\n", stderr=stderr),
    )
    ctx = _RecordingContext()
    result = json.loads(
        await execute_manim_code(
            code="from manim_slides import Slide\nclass MySlide(Slide): pass\n",
            scenes=["MySlide"],
            media_dir=str(tmp_path),
            ctx=ctx,
        )
    )
    assert result["success"] is True
    percentages = [report[0] for report in ctx.reports]
    assert 0.0 in percentages
    assert 50.0 in percentages
    assert 100.0 in percentages
    messages = [report[2] or "" for report in ctx.reports]
    assert any("1/2 frames" in message for message in messages)


def test_render_cache_key_deterministic():
    """Verify the cache key is stable for identical inputs and varies otherwise."""
    code = "class MySlide(Slide): pass"
    key_a = _render_cache_key(code, ["MySlide"], "l")
    key_b = _render_cache_key(code, ["MySlide"], "l")
    assert key_a == key_b
    assert key_a != _render_cache_key(code, ["OtherSlide"], "l")
    assert key_a != _render_cache_key(code, ["MySlide"], "h")
    assert key_a != _render_cache_key("class Other(Slide): pass", ["MySlide"], "l")


def test_render_cache_roundtrip(tmp_path):
    """Verify files saved to the cache are restored with their relative layout."""
    source = tmp_path / "videos" / "480p15" / "MySlide.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("fake-video")
    key = _render_cache_key("code", ["MySlide"], "l")
    _save_render_cache(tmp_path, key, [str(source)])

    files = _load_render_cache(tmp_path, key)
    assert files == ["videos/480p15/MySlide.mp4"]

    source.unlink()
    restored = _restore_render_cache(tmp_path, key, files)
    assert restored == [str((tmp_path / "videos/480p15/MySlide.mp4").resolve())]
    assert (tmp_path / "videos/480p15/MySlide.mp4").read_text() == "fake-video"


def test_render_cache_miss(tmp_path):
    """Verify an unknown key returns None."""
    assert _load_render_cache(tmp_path, "does-not-exist") is None


@pytest.mark.anyio
async def test_execute_manim_code_cache_hit_skips_render(monkeypatch, tmp_path):
    """Verify unchanged code is served from cache without re-rendering."""
    calls: list[tuple] = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        media_dir = Path(kwargs["cwd"])
        video = media_dir / "videos" / "480p15" / "MySlide.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_text("fake")
        config = media_dir / "slides" / "MySlide.json"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text("{}")
        return _FakeAsyncProcess(0, stdout=b"Rendered")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    code = "from manim_slides import Slide\nclass MySlide(Slide): pass\n"

    first = json.loads(
        await execute_manim_code(code=code, scenes=["MySlide"], media_dir=str(tmp_path))
    )
    assert first["success"] is True
    assert "cached" not in first
    assert first["scene_cache"] == {"MySlide": False}
    assert len(calls) == 1

    second = json.loads(
        await execute_manim_code(code=code, scenes=["MySlide"], media_dir=str(tmp_path))
    )
    assert second["success"] is True
    assert second["cached"] is True
    assert second["scene_cache"] == {"MySlide": True}
    assert any(f.endswith("MySlide.mp4") for f in second["media_files"])
    assert len(calls) == 1


@pytest.mark.anyio
async def test_execute_manim_code_disable_cache(monkeypatch, tmp_path):
    """Verify use_cache=False always re-renders and never reports a cache hit."""
    calls: list[tuple] = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        media_dir = Path(kwargs["cwd"])
        video = media_dir / "videos" / "480p15" / "MySlide.mp4"
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_text("fake")
        return _FakeAsyncProcess(0, stdout=b"Rendered")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    code = "from manim_slides import Slide\nclass MySlide(Slide): pass\n"

    first = json.loads(
        await execute_manim_code(
            code=code, scenes=["MySlide"], media_dir=str(tmp_path), use_cache=False
        )
    )
    second = json.loads(
        await execute_manim_code(
            code=code, scenes=["MySlide"], media_dir=str(tmp_path), use_cache=False
        )
    )
    assert first["success"] is True
    assert second["success"] is True
    assert "cached" not in first
    assert "cached" not in second
    assert first["scene_cache"] == {"MySlide": False}
    assert second["scene_cache"] == {"MySlide": False}
    assert len(calls) == 2


FRAGMENT_CODE = (
    "from manim_slides import Slide\n"
    "\n"
    "def helper():\n"
    "    return 1\n"
    "\n"
    "class A(Slide):\n"
    "    def construct(self):\n"
    "        pass\n"
    "\n"
    "class B(Slide):\n"
    "    def construct(self):\n"
    "        pass\n"
)


def test_extract_scene_fragments_captures_preamble_and_classes():
    """Verify class sources are exact and shared helpers land in the preamble."""
    preamble, fragments = _extract_scene_fragments(FRAGMENT_CODE)
    assert fragments == {
        "A": "class A(Slide):\n    def construct(self):\n        pass",
        "B": "class B(Slide):\n    def construct(self):\n        pass",
    }
    assert preamble == "from manim_slides import Slide\ndef helper():\n    return 1"
    assert "def helper" in preamble
    assert "from manim_slides import Slide" in preamble
    assert "class A" not in preamble
    assert "class B" not in preamble
    assert "class A" not in fragments["B"]


def test_extract_scene_fragments_includes_decorators():
    """Verify decorator lines are part of the owning scene's source."""
    preamble, fragments = _extract_scene_fragments("@echo\nclass A(Slide):\n    pass\n")
    assert preamble == ""
    assert fragments == {"A": "@echo\nclass A(Slide):\n    pass"}


def test_extract_scene_fragments_invalid_code():
    """Verify invalid code degrades to an empty result instead of raising."""
    assert _extract_scene_fragments("def broken(:\n") == ("", {})


def test_scene_cache_key_stability_and_sensitivity():
    """Verify editing one scene only changes that scene's cache key."""
    code_one = (
        "class A(Slide):\n"
        "    def construct(self):\n"
        "        x = 1\n"
        "class B(Slide):\n"
        "    def construct(self):\n"
        "        x = 2\n"
    )
    code_two = code_one.replace("        x = 1\n", "        x = 99\n")
    preamble_one, fragments_one = _extract_scene_fragments(code_one)
    preamble_two, fragments_two = _extract_scene_fragments(code_two)
    assert preamble_one == preamble_two

    key_a_one = _scene_cache_key(preamble_one, fragments_one["A"], "l")
    key_a_two = _scene_cache_key(preamble_two, fragments_two["A"], "l")
    key_b_one = _scene_cache_key(preamble_one, fragments_one["B"], "l")
    key_b_two = _scene_cache_key(preamble_two, fragments_two["B"], "l")

    assert key_a_one != key_a_two
    assert key_b_one == key_b_two
    assert key_b_one == _scene_cache_key(preamble_one, fragments_one["B"], "l")
    assert key_b_one != _scene_cache_key(preamble_one, fragments_one["B"], "h")


def test_scene_cache_key_shared_helper_change_invalidates_all():
    """Verify a preamble change flips every scene's key."""
    code_one = "def helper():\n    return 1\nclass A(Slide):\n    pass\n"
    code_two = "def helper():\n    return 2\nclass A(Slide):\n    pass\n"
    preamble_one, fragments_one = _extract_scene_fragments(code_one)
    preamble_two, fragments_two = _extract_scene_fragments(code_two)
    assert preamble_one != preamble_two
    assert _scene_cache_key(preamble_one, fragments_one["A"], "l") != _scene_cache_key(
        preamble_two, fragments_two["A"], "l"
    )


@pytest.mark.anyio
async def test_execute_manim_code_partial_cache_hit_renders_only_missed(
    monkeypatch, tmp_path
):
    """Verify cached scenes are restored and only misses reach the renderer."""
    code = (
        "class A(Slide):\n"
        "    def construct(self):\n"
        "        pass\n"
        "class B(Slide):\n"
        "    def construct(self):\n"
        "        pass\n"
    )
    preamble, fragments = _extract_scene_fragments(code)
    key_a = _scene_cache_key(preamble, fragments["A"], "l")
    key_b = _scene_cache_key(preamble, fragments["B"], "l")
    seeded_video = tmp_path / "videos" / "480p15" / "A.mp4"
    seeded_video.parent.mkdir(parents=True, exist_ok=True)
    seeded_video.write_text("cached-a")
    seeded_config = tmp_path / "slides" / "A.json"
    seeded_config.parent.mkdir(parents=True, exist_ok=True)
    seeded_config.write_text("{}")
    _save_render_cache(tmp_path, key_a, [str(seeded_video), str(seeded_config)])

    render_calls: list[list[str]] = []

    async def fake_render(
        command, workspace, scenes, quality, start, timeout, ctx=None
    ):
        render_calls.append(list(scenes))
        media_files = []
        for scene in scenes:
            video = workspace / "videos" / "480p15" / f"{scene}.mp4"
            video.parent.mkdir(parents=True, exist_ok=True)
            video.write_text("fake")
            media_files.append(str(video))
            config = workspace / "slides" / f"{scene}.json"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text("{}")
        return {
            "success": True,
            "scenes": scenes,
            "quality": quality,
            "media_dir": str(workspace.resolve()),
            "media_files": media_files,
            "command": command,
            "stdout": "Rendered",
            "stderr": "",
        }

    monkeypatch.setattr(
        "mcp_manim_slides.server._run_render_streaming", fake_render
    )
    result = json.loads(
        await execute_manim_code(
            code=code, scenes=["A", "B"], media_dir=str(tmp_path)
        )
    )
    assert result["success"] is True
    assert render_calls == [["B"]]
    assert result["scene_cache"] == {"A": True, "B": False}
    assert result["scenes"] == ["A", "B"]
    assert any(f.endswith("A.mp4") for f in result["media_files"])
    assert any(f.endswith("B.mp4") for f in result["media_files"])
    assert _load_render_cache(tmp_path, key_b) is not None


def _fake_render_streaming(calls: list[list[str]]):
    """Return an async ``_run_render_streaming`` stand-in that records scenes."""

    async def fake(command, workspace, scenes, quality, start, timeout, ctx=None):
        calls.append(list(scenes))
        media_files = []
        for scene in scenes:
            video = workspace / "videos" / "480p15" / f"{scene}.mp4"
            video.parent.mkdir(parents=True, exist_ok=True)
            video.write_text("fake")
            media_files.append(str(video))
            config = workspace / "slides" / f"{scene}.json"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text("{}")
        return {
            "success": True,
            "scenes": scenes,
            "quality": quality,
            "media_dir": str(workspace.resolve()),
            "media_files": media_files,
            "command": command,
            "stdout": "Rendered",
            "stderr": "",
        }

    return fake


def _fake_convert(calls: list[dict]):
    """Return a ``_run_convert`` stand-in that records convert invocations."""

    def fake(command, dest, scenes, output_format, cwd, timeout):
        calls.append({"dest": dest, "scenes": list(scenes)})
        destination = Path(cwd).joinpath(dest).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("<html>deck</html>")
        return json.dumps(
            {
                "success": True,
                "format": output_format,
                "destination": str(destination),
                "scenes": scenes,
                "command": command,
                "stdout": "",
                "stderr": "",
            }
        )

    return fake


def test_sync_deck_renders_reuses_and_removes(monkeypatch, tmp_path):
    """Verify sync renders once, reuses cached scenes, and reports removals."""
    render_calls: list[list[str]] = []
    convert_calls: list[dict] = []
    monkeypatch.setattr(
        "mcp_manim_slides.server._run_render_streaming",
        _fake_render_streaming(render_calls),
    )
    monkeypatch.setattr(
        "mcp_manim_slides.server._run_convert", _fake_convert(convert_calls)
    )

    code_both = (
        "class A(Slide):\n"
        "    def construct(self):\n"
        "        pass\n"
        "class B(Slide):\n"
        "    def construct(self):\n"
        "        pass\n"
    )

    first = json.loads(
        sync_deck(code=code_both, media_dir=str(tmp_path), dest="deck.html")
    )
    assert first["success"] is True
    assert first["rendered"] == ["A", "B"]
    assert first["reused"] == []
    assert first["removed"] == []
    assert first["scene_cache"] == {"A": False, "B": False}
    assert render_calls == [["A", "B"]]
    assert first["dest"].endswith("deck.html")
    state_path = tmp_path / ".sync_state.json"
    state = json.loads(state_path.read_text())
    assert set(state["scenes"]) == {"A", "B"}

    second = json.loads(
        sync_deck(code=code_both, media_dir=str(tmp_path), dest="deck.html")
    )
    assert second["success"] is True
    assert second["rendered"] == []
    assert second["reused"] == ["A", "B"]
    assert second["scene_cache"] == {"A": True, "B": True}
    assert render_calls == [["A", "B"]]

    code_edited = code_both.replace(
        "class B(Slide):\n    def construct(self):\n        pass",
        "class B(Slide):\n    def construct(self):\n        step = 1",
    )
    third = json.loads(
        sync_deck(code=code_edited, media_dir=str(tmp_path), dest="deck.html")
    )
    assert third["success"] is True
    assert third["rendered"] == ["B"]
    assert third["reused"] == ["A"]
    assert third["scene_cache"] == {"A": True, "B": False}
    assert render_calls == [["A", "B"], ["B"]]

    code_only_a = (
        "class A(Slide):\n"
        "    def construct(self):\n"
        "        pass\n"
    )
    fourth = json.loads(
        sync_deck(code=code_only_a, media_dir=str(tmp_path), dest="deck.html")
    )
    assert fourth["success"] is True
    assert fourth["removed"] == ["B"]
    assert fourth["rendered"] == []
    assert fourth["reused"] == ["A"]
    assert render_calls == [["A", "B"], ["B"]]
    state = json.loads(state_path.read_text())
    assert set(state["scenes"]) == {"A"}
    assert convert_calls[-1]["scenes"] == ["A"]


def test_sync_deck_syntax_error_envelope(tmp_path):
    """Verify invalid code fails fast without touching the sync state."""
    result = json.loads(sync_deck(code="def broken(:\n", media_dir=str(tmp_path)))
    assert result["success"] is False
    assert "SyntaxError" in result["error"]
    assert not (tmp_path / ".sync_state.json").exists()


def test_sync_deck_render_failure_returns_error_envelope(monkeypatch, tmp_path):
    """Verify render failures keep the error envelope and skip state writes."""

    async def fake_fail(command, workspace, scenes, quality, start, timeout, ctx=None):
        return {
            "success": False,
            "scenes": scenes,
            "quality": quality,
            "media_dir": str(workspace.resolve()),
            "media_files": [],
            "command": command,
            "stdout": "",
            "stderr": "ModuleNotFoundError: No module named 'numpy'",
            "error": "ModuleNotFoundError: No module named 'numpy'",
            "missing_dependency": "numpy",
            "hint": "The Python module 'numpy' is not installed. "
            "Install it with 'pip install numpy'.",
        }

    monkeypatch.setattr("mcp_manim_slides.server._run_render_streaming", fake_fail)
    result = json.loads(
        sync_deck(
            code="class A(Slide):\n    def construct(self):\n        pass\n",
            media_dir=str(tmp_path),
        )
    )
    assert result["success"] is False
    assert "ModuleNotFoundError" in result["error"]
    assert result["missing_dependency"] == "numpy"
    assert "pip install numpy" in result["hint"]
    assert not (tmp_path / ".sync_state.json").exists()


def test_sync_deck_no_scenes_reports_error(tmp_path):
    """Verify code without scene classes is rejected before any subprocess."""
    result = json.loads(
        sync_deck(code="def helper():\n    return 1\n", media_dir=str(tmp_path))
    )
    assert result["success"] is False
    assert "No scenes to sync" in result["error"]


def test_parse_render_progress_full_bar():
    """Verify a complete tqdm bar is parsed into percent, frames, and desc."""
    progress = _parse_render_progress(
        "Animation 0: FadeIn(Circle):  50%|█████     | 1/2 [00:01<00:01, 1.00it/s]"
    )
    assert progress is not None
    assert progress.percent == 50.0
    assert progress.current == 1
    assert progress.total == 2
    assert progress.description == "Animation 0: FadeIn(Circle)"


def test_parse_render_progress_unknown_total():
    """Verify a bar with an unknown total (``?``) yields ``total=None``."""
    progress = _parse_render_progress("  0%|          | 0/? [00:00<?, ?it/s]")
    assert progress is not None
    assert progress.percent == 0.0
    assert progress.current == 0
    assert progress.total is None


def test_parse_render_progress_ignores_non_progress_lines():
    """Verify non-tqdm lines are ignored."""
    assert _parse_render_progress("Rendering scene: MySlide") is None
    assert _parse_render_progress("") is None


def test_format_progress_message():
    """Verify progress messages include frames and percentage."""
    progress = RenderProgress(
        percent=50.0,
        current=1,
        total=2,
        description="Animation 0: FadeIn(Circle)",
    )
    message = _format_progress_message(progress)
    assert "Animation 0: FadeIn(Circle)" in message
    assert "1/2 frames" in message
    assert "50%" in message


@pytest.mark.anyio
async def test_server_call_tool_hides_context_param():
    """Verify the injected context parameter is not exposed in the schema."""
    tools = await mcp.list_tools()
    exec_tool = next(t for t in tools if t.name == "execute_manim_code")
    assert "ctx" not in exec_tool.input_schema["properties"]
    assert "code" in exec_tool.input_schema["properties"]


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


@pytest.mark.anyio
async def test_server_list_tools_includes_sync_deck():
    """Verify sync_deck tool is registered on the MCPServer."""
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "sync_deck" in tool_names

    sync_tool = next(t for t in tools if t.name == "sync_deck")
    assert "code" in sync_tool.input_schema["properties"]
    assert "dest" in sync_tool.input_schema["properties"]
    assert "quality" in sync_tool.input_schema["properties"]
    assert "ctx" not in sync_tool.input_schema["properties"]


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


def test_slides_list_resource(monkeypatch, tmp_path):
    """Verify the slides://list resource reads the active WORKSPACE_DIR."""
    _write_scene_config(
        tmp_path,
        "MySlide",
        [
            {"type": "video", "file": "slides/files/MySlide/0.mp4"},
            {"type": "video", "file": "slides/files/MySlide/1.mp4"},
        ],
    )
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    result = json.loads(slides_list())
    assert result["success"] is True
    assert result["scene_count"] == 1
    assert result["scenes"][0]["scene"] == "MySlide"
    assert result["scenes"][0]["slide_count"] == 2


def test_slides_list_resource_missing_folder(monkeypatch, tmp_path):
    """Verify the slides://list resource reports a missing slides folder."""
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))
    result = json.loads(slides_list())
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
    monkeypatch.setattr(
        "mcp_manim_slides.server._ffmpeg_executable",
        lambda: "/usr/bin/ffmpeg",
    )

    result = json.loads(preview_slide(scene="MySlide", workspace_dir=str(tmp_path)))
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


def test_preview_slide_webm_to_mp4_transcode(monkeypatch, tmp_path):
    """Verify preview_slide transcodes non-mp4 media instead of renaming it."""
    _write_scene_config(
        tmp_path,
        "MySlide",
        [{"type": "video", "file": "slides/files/MySlide/0.webm"}],
    )

    captured: dict[str, list] = {}

    def fake_run(command, **kwargs):
        captured["command"] = list(command)
        destination = Path(command[-1])
        destination.write_text("fake-mp4")
        return _FakeCompletedProcess(0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        "mcp_manim_slides.server._ffmpeg_executable",
        lambda: "/usr/bin/ffmpeg",
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
    assert captured["command"][0] == "/usr/bin/ffmpeg"
    assert captured["command"][-1].endswith("MySlide_0.mp4")


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
    result = json.loads(preview_slide(scene="Nope", workspace_dir=str(tmp_path)))
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


@pytest.fixture(autouse=True)
def _cleanup_preview_servers():
    """Stop any preview servers started during a test after it finishes."""
    yield
    stop_preview_server()


def test_serve_revealjs_html_missing_file(tmp_path):
    """Verify serve_revealjs_html reports an error for a missing deck."""
    result = json.loads(
        serve_revealjs_html(dest="nope.html", workspace_dir=str(tmp_path))
    )
    assert result["success"] is False
    assert "not found" in result["error"]


def test_serve_revealjs_html_rejects_non_html(tmp_path):
    """Verify serve_revealjs_html rejects a non-HTML file."""
    (tmp_path / "deck.pdf").write_text("not html")
    result = json.loads(
        serve_revealjs_html(dest="deck.pdf", workspace_dir=str(tmp_path))
    )
    assert result["success"] is False
    assert ".html" in result["error"]


def test_serve_revealjs_html_success_and_fetch(tmp_path):
    """Verify the deck is served and its content is reachable over HTTP."""
    (tmp_path / "deck.html").write_text("<html>deck</html>")
    result = json.loads(
        serve_revealjs_html(
            dest="deck.html",
            workspace_dir=str(tmp_path),
            open_browser=False,
        )
    )
    assert result["success"] is True
    assert result["port"] > 0
    assert result["url"].endswith("/deck.html")
    assert result["reused"] is False
    assert result["browser_opened"] is False

    with urllib.request.urlopen(result["url"], timeout=5) as response:
        assert b"deck" in response.read()


def test_serve_revealjs_html_reuses_server(tmp_path):
    """Verify a second serve call reuses the existing server for a directory."""
    (tmp_path / "deck.html").write_text("<html>deck</html>")
    first = json.loads(
        serve_revealjs_html(
            dest="deck.html",
            workspace_dir=str(tmp_path),
            open_browser=False,
        )
    )
    second = json.loads(
        serve_revealjs_html(
            dest="deck.html",
            workspace_dir=str(tmp_path),
            open_browser=False,
        )
    )
    assert first["success"] is True
    assert second["success"] is True
    assert second["reused"] is True
    assert second["port"] == first["port"]


def test_stop_preview_server_by_port(tmp_path):
    """Verify stop_preview_server shuts down the server bound to a port."""
    (tmp_path / "deck.html").write_text("<html>deck</html>")
    result = json.loads(
        serve_revealjs_html(
            dest="deck.html",
            workspace_dir=str(tmp_path),
            open_browser=False,
        )
    )
    port = result["port"]
    stop = json.loads(stop_preview_server(port=port))
    assert stop["success"] is True
    assert port in stop["stopped_ports"]
    assert stop["remaining"] == 0


def test_stop_preview_server_all(tmp_path):
    """Verify stop_preview_server without a port stops every preview server."""
    (tmp_path / "deck.html").write_text("<html>deck</html>")
    serve_revealjs_html(
        dest="deck.html", workspace_dir=str(tmp_path), open_browser=False
    )
    stop = json.loads(stop_preview_server())
    assert stop["success"] is True
    assert len(stop["stopped_ports"]) == 1
    assert stop["remaining"] == 0


@pytest.mark.anyio
async def test_server_list_tools_includes_serve_and_stop():
    """Verify serve_revealjs_html and stop_preview_server are registered."""
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "serve_revealjs_html" in tool_names
    assert "stop_preview_server" in tool_names

    serve_tool = next(t for t in tools if t.name == "serve_revealjs_html")
    assert "dest" in serve_tool.input_schema["properties"]
    assert "port" in serve_tool.input_schema["properties"]
    assert "open_browser" in serve_tool.input_schema["properties"]


ALL_PROMPT_NAMES = {
    "title_slide",
    "agenda",
    "code_walkthrough",
    "math_derivation",
    "two_column_comparison",
}


def _prompt_text(result) -> str:
    """Return the concatenated text of a GetPromptResult's messages."""
    return "\n".join(message.content.text for message in result.messages)


@pytest.mark.anyio
async def test_server_list_prompts():
    """Verify all five slide-archetype prompts are registered."""
    prompts = await mcp.list_prompts()
    names = {prompt.name for prompt in prompts}
    assert ALL_PROMPT_NAMES <= names


@pytest.mark.anyio
async def test_prompt_title_slide_includes_title():
    """Verify title_slide embeds the given title and chaining instructions."""
    result = await mcp.get_prompt(
        "title_slide",
        {
            "title": "Quantum Computing 101",
            "subtitle": "A gentle introduction",
            "author": "Ada Lovelace",
        },
    )
    text = _prompt_text(result)
    assert "Quantum Computing 101" in text
    assert "A gentle introduction" in text
    assert "Ada Lovelace" in text
    assert "self.next_slide()" in text
    assert "execute_manim_code" in text
    assert "export_revealjs_html" in text


@pytest.mark.anyio
async def test_prompt_agenda_parses_comma_separated_topics():
    """Verify agenda splits a comma-separated topics string into a list."""
    result = await mcp.get_prompt("agenda", {"topics": "Intro, Demo, Results"})
    text = _prompt_text(result)
    assert "1. Intro" in text
    assert "2. Demo" in text
    assert "3. Results" in text


@pytest.mark.anyio
async def test_prompt_code_walkthrough_embeds_code_verbatim():
    """Verify code_walkthrough keeps the supplied code intact in the body."""
    snippet = "def answer():\n    return {'value': 42}"
    result = await mcp.get_prompt(
        "code_walkthrough", {"code": snippet, "title": "Deep Dive"}
    )
    text = _prompt_text(result)
    assert snippet in text
    assert "Deep Dive" in text


@pytest.mark.anyio
async def test_prompt_math_derivation_lists_steps():
    """Verify math_derivation splits comma-separated LaTeX steps."""
    result = await mcp.get_prompt(
        "math_derivation", {"steps": "f(x) = x^2, f'(x) = 2x", "title": "Calculus"}
    )
    text = _prompt_text(result)
    assert "1. f(x) = x^2" in text
    assert "2. f'(x) = 2x" in text
    assert "Calculus" in text


@pytest.mark.anyio
async def test_prompt_two_column_comparison_lists_both_sides():
    """Verify two_column_comparison renders both columns' titles and points."""
    result = await mcp.get_prompt(
        "two_column_comparison",
        {
            "left_title": "Pros",
            "right_title": "Cons",
            "left_points": "Fast, Cheap",
            "right_points": "Limited, Buggy",
        },
    )
    text = _prompt_text(result)
    assert "Pros" in text
    assert "Cons" in text
    assert "1. Fast" in text
    assert "2. Cheap" in text
    assert "1. Limited" in text
    assert "2. Buggy" in text


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("title_slide", {"title": "T"}),
        ("agenda", {"topics": "A"}),
        ("code_walkthrough", {"code": "pass"}),
        ("math_derivation", {"steps": "x = 1"}),
        (
            "two_column_comparison",
            {
                "left_title": "L",
                "right_title": "R",
                "left_points": "p1",
                "right_points": "p2",
            },
        ),
    ],
)
async def test_prompt_bodies_include_mechanics_and_toolchain(name, arguments):
    """Verify every archetype body teaches slide mechanics and the tool chain."""
    result = await mcp.get_prompt(name, arguments)
    text = _prompt_text(result)
    assert "Slide" in text
    assert "self.next_slide()" in text
    assert "```python" in text
    assert "execute_manim_code" in text
    assert "preview_slide" in text
    assert "export_revealjs_html" in text
    assert "compile_presentation" in text


@pytest.mark.anyio
async def test_prompt_missing_required_argument_raises():
    """Verify the SDK rejects a prompts/get call missing required arguments."""
    with pytest.raises(ValueError, match="Missing required arguments"):
        await mcp.get_prompt("title_slide", {})
def test_build_export_command_transition_none():
    """Verify transition=none builds normalize commands plus a concat list."""
    commands = _build_export_command(
        media=[
            {"path": "slides/a.mp4", "type": "video"},
            {"path": "slides/b.png", "type": "image"},
        ],
        dest="presentation.mp4",
        width=854,
        height=480,
        segment_paths=["seg0.mp4", "seg1.mp4"],
        fps=30,
        transition="none",
        image_duration=2.0,
        concat_list_path="concat.txt",
    )
    assert len(commands) == 3
    video_command, image_command, final_command = commands
    assert "-loop" not in video_command
    assert image_command[image_command.index("-loop") + 1] == "1"
    assert image_command[image_command.index("-t") + 1] == "2.0"
    for command in (video_command, image_command):
        assert "-c:v" in command
        assert "libx264" in command
        assert "yuv420p" in command
        video_filter = command[command.index("-vf") + 1]
        assert "scale=854:480:force_original_aspect_ratio=decrease" in video_filter
        assert "pad=854:480:(ow-iw)/2:(oh-ih)/2" in video_filter
        assert "fps=30" in video_filter
    assert final_command[final_command.index("-f") + 1] == "concat"
    assert final_command[final_command.index("-i") + 1] == "concat.txt"
    assert "xfade" not in "".join(final_command)
    assert final_command[-1] == "presentation.mp4"


def test_concat_list_text_lists_segments():
    """Verify the concat demuxer list file references every segment."""
    text = _concat_list_text(["seg0.mp4", "seg1.mp4"])
    assert text == "file 'seg0.mp4'\nfile 'seg1.mp4'\n"


def test_build_export_command_transition_fade():
    """Verify transition=fade builds an xfade chain with measured offsets."""
    commands = _build_export_command(
        media=[
            {"path": "slides/a.mp4", "type": "video"},
            {"path": "slides/b.png", "type": "image"},
            {"path": "slides/c.mp4", "type": "video"},
        ],
        dest="presentation.mp4",
        width=640,
        height=360,
        segment_paths=["seg0.mp4", "seg1.mp4", "seg2.mp4"],
        fps=30,
        transition="fade",
        transition_duration=0.5,
        image_duration=2.0,
        concat_list_path="concat.txt",
        durations=[2.0, 3.0, 1.5],
    )
    assert len(commands) == 4
    image_command = commands[1]
    assert image_command[image_command.index("-loop") + 1] == "1"
    final_command = commands[-1]
    filter_arg = final_command[final_command.index("-filter_complex") + 1]
    assert "xfade=transition=fade" in filter_arg
    assert "duration=0.5" in filter_arg
    assert "offset=1.5" in filter_arg
    assert "offset=4.0" in filter_arg
    assert final_command[final_command.index("-map") + 1] == "[x2]"
    assert "concat" not in "".join(final_command)
    assert final_command[-1] == "presentation.mp4"


def test_ffprobe_duration_parses_stdout(monkeypatch):
    """Verify _ffprobe_duration parses the ffprobe duration output."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(0, stdout="2.5\n"),
    )
    assert _ffprobe_duration("clip.mp4") == 2.5


def test_ffprobe_duration_returns_none_on_failure(monkeypatch):
    """Verify _ffprobe_duration returns None when the probe fails."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(1, stderr="boom"),
    )
    assert _ffprobe_duration("clip.mp4") is None

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(0, stdout="N/A"),
    )
    assert _ffprobe_duration("clip.mp4") is None

    def missing_ffprobe(*args, **kwargs):
        raise FileNotFoundError("ffprobe")

    monkeypatch.setattr(subprocess, "run", missing_ffprobe)
    assert _ffprobe_duration("clip.mp4") is None


def test_export_video_success(monkeypatch, tmp_path):
    """Verify export_video assembles the segments into one MP4."""
    _write_scene_config(
        tmp_path,
        "Intro",
        [
            {"type": "video", "file": "slides/files/Intro/0.mp4"},
            {"type": "image", "file": "slides/files/Intro/1.png"},
        ],
    )
    _write_scene_config(
        tmp_path,
        "Outro",
        [{"type": "video", "file": "slides/files/Outro/0.mp4"}],
    )
    captured: list[list[str]] = []

    def fake_run(command, **kwargs):
        captured.append(list(command))
        if command[0] == "ffprobe":
            return _FakeCompletedProcess(0, stdout="2.0\n")
        destination = Path(command[-1])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("fake")
        return _FakeCompletedProcess(0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        "mcp_manim_slides.server._ffmpeg_executable",
        lambda: "/usr/bin/ffmpeg",
    )

    result = json.loads(
        export_video(
            scenes=["Intro", "Outro"],
            dest="presentation.mp4",
            workspace_dir=str(tmp_path),
        )
    )
    assert result["success"] is True
    assert result["dest"] == str((tmp_path / "presentation.mp4").resolve())
    assert result["scenes"] == ["Intro", "Outro"]
    assert result["slide_count"] == 3
    assert result["transition"] == "none"
    assert result["duration"] == 6.0
    assert result["command"][0] == "/usr/bin/ffmpeg"
    ffmpeg_commands = [c for c in captured if c[0] != "ffprobe"]
    final_command = ffmpeg_commands[-1]
    assert final_command[final_command.index("-f") + 1] == "concat"
    normalize_commands = ffmpeg_commands[:-1]
    assert [Path(c[-1]).name for c in normalize_commands] == [
        "segment_000.mp4",
        "segment_001.mp4",
        "segment_002.mp4",
    ]
    assert any("-loop" in c for c in normalize_commands)


def test_export_video_fade_builds_xfade_offsets(monkeypatch, tmp_path):
    """Verify export_video measures segments and chains xfades with offsets."""
    _write_scene_config(
        tmp_path,
        "Intro",
        [
            {"type": "video", "file": "slides/files/Intro/0.mp4"},
            {"type": "video", "file": "slides/files/Intro/1.mp4"},
        ],
    )
    captured: list[list[str]] = []

    def fake_run(command, **kwargs):
        captured.append(list(command))
        if command[0] == "ffprobe":
            return _FakeCompletedProcess(0, stdout="2.0\n")
        destination = Path(command[-1])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("fake")
        return _FakeCompletedProcess(0, stdout="ok")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        "mcp_manim_slides.server._ffmpeg_executable",
        lambda: "/usr/bin/ffmpeg",
    )

    result = json.loads(
        export_video(
            scenes=["Intro"],
            dest="presentation.mp4",
            workspace_dir=str(tmp_path),
            transition="fade",
            transition_duration=0.5,
        )
    )
    assert result["success"] is True
    assert result["transition"] == "fade"
    assert result["duration"] == 3.5
    final_command = [c for c in captured if c[0] != "ffprobe"][-1]
    filter_arg = final_command[final_command.index("-filter_complex") + 1]
    assert "xfade=transition=fade" in filter_arg
    assert "offset=1.5" in filter_arg
    assert final_command[final_command.index("-map") + 1] == "[x1]"


def test_export_video_missing_media(tmp_path):
    """Verify export_video lists every missing slide media file."""
    slides_dir = tmp_path / "slides"
    slides_dir.mkdir()
    (slides_dir / "Intro.json").write_text(
        json.dumps(
            {
                "slides": [
                    {"type": "video", "file": "slides/files/Intro/0.mp4"},
                    {"type": "image", "file": "slides/files/Intro/1.png"},
                ],
                "resolution": [854, 480],
            }
        )
    )
    result = json.loads(export_video(scenes=["Intro"], workspace_dir=str(tmp_path)))
    assert result["success"] is False
    assert "not found" in result["error"]
    assert "slides/files/Intro/0.mp4" in result["error"]
    assert "slides/files/Intro/1.png" in result["error"]


def test_export_video_missing_scene(tmp_path):
    """Verify export_video reports a missing scene before invoking ffmpeg."""
    result = json.loads(export_video(scenes=["Nope"], workspace_dir=str(tmp_path)))
    assert result["success"] is False
    assert "not found" in result["error"]


def test_export_video_invalid_transition(tmp_path):
    """Verify export_video rejects unsupported transitions."""
    result = json.loads(
        export_video(
            scenes=["Intro"],
            transition="wipe",
            workspace_dir=str(tmp_path),
        )
    )
    assert result["success"] is False
    assert "Invalid transition 'wipe'" in result["error"]


def test_export_video_missing_ffmpeg(monkeypatch, tmp_path):
    """Verify export_video fails fast with an actionable ffmpeg error."""
    _write_scene_config(
        tmp_path,
        "Intro",
        [{"type": "video", "file": "slides/files/Intro/0.mp4"}],
    )
    monkeypatch.setattr("mcp_manim_slides.server._ffmpeg_executable", lambda: None)
    result = json.loads(export_video(scenes=["Intro"], workspace_dir=str(tmp_path)))
    assert result["success"] is False
    assert "ffmpeg executable not found" in result["error"]


@pytest.mark.anyio
async def test_server_list_tools_includes_export_video():
    """Verify export_video tool is registered on the MCPServer."""
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "export_video" in tool_names

    export_tool = next(t for t in tools if t.name == "export_video")
    assert "MP4" in export_tool.description
    assert "scenes" in export_tool.input_schema["properties"]
    assert "transition" in export_tool.input_schema["properties"]
    assert "image_duration" in export_tool.input_schema["properties"]
