"""Manim-Slides Model Context Protocol (MCP) Server.

Provides tools for AI agents to generate, execute, and compile
interactive presentations using Manim Community and Manim-Slides.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.context import Context

# Initialize MCP Server with official v2 SDK
mcp = MCPServer(
    name="manim-slides-server",
    version="0.1.0",
    description="MCP server for generating and compiling Manim-Slides presentations",
)


@mcp.resource("status://server")
def server_status() -> str:
    """Return the current status and environment info of the MCP server."""
    python_version = sys.version.split()[0]
    return f"Manim-Slides MCP Server is running (Python {python_version})"


@mcp.resource("revealjs://config")
def revealjs_config_options() -> str:
    """Return the supported Reveal.js HTML export configuration options."""
    return json.dumps(
        {
            "themes": list(REVEAL_THEMES),
            "transitions": list(REVEAL_TRANSITIONS),
            "transition_speeds": list(REVEAL_TRANSITION_SPEEDS),
            "boolean_options": [
                "controls",
                "progress",
                "slide_number",
                "hash",
                "loop",
            ],
            "defaults": {
                "theme": "black",
                "transition": "none",
                "transition_speed": "default",
                "controls": False,
                "progress": False,
                "slide_number": False,
                "hash": False,
                "loop": False,
                "one_file": False,
                "offline": False,
            },
        },
        indent=2,
    )


@mcp.resource("slides://list")
def slides_list() -> str:
    """List all rendered slide configurations and metadata in the workspace.

    Reads the slide configuration files (``<scene>.json``) produced by
    ``manim-slides render`` from the default ``slides`` folder inside the
    active workspace (``WORKSPACE_DIR`` environment variable or the current
    directory). Unlike the ``list_scenes`` tool, this read-only resource
    always targets the active workspace and takes no arguments.

    Returns:
        A JSON string listing the discovered scenes and their slide metadata.
    """
    cwd = os.environ.get("WORKSPACE_DIR")
    folder_path = Path(cwd or ".").joinpath("slides")
    if not folder_path.is_dir():
        return json.dumps(
            {
                "success": False,
                "error": f"Slides folder not found: {folder_path}",
            }
        )
    scenes = _collect_scene_metadata(folder_path)
    return json.dumps(
        {
            "success": True,
            "folder": str(folder_path.resolve()),
            "scene_count": len(scenes),
            "scenes": scenes,
        },
        indent=2,
    )


@mcp.tool()
def hello_world(name: str = "World") -> str:
    """A basic Hello World tool to verify client-server communication.

    Args:
        name: The name of the person or entity to greet. Defaults to 'World'.

    Returns:
        A greeting message confirming successful MCP communication.
    """
    try:
        return f"Hello, {name}! Manim-Slides MCP server is reachable and operational."
    except Exception as e:
        return f"Error executing hello_world tool: {e}"


def _manim_slides_executable() -> list[str]:
    """Return the command prefix used to invoke the manim-slides CLI."""
    executable = shutil.which("manim-slides")
    if executable:
        return [executable]
    return [sys.executable, "-m", "manim_slides"]


def _module_available(name: str) -> bool:
    """Return True if ``name`` is importable.

    Guards against packages whose ``__spec__`` is ``None`` (which makes
    ``importlib.util.find_spec`` raise ``ValueError`` even though the module is
    already importable).
    """
    if name in sys.modules:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _manim_slides_availability_error() -> str | None:
    """Return a clear error if manim-slides cannot be invoked, else None.

    Checks both the ``manim-slides`` console script and the ``manim_slides``
    Python module so rendering/compilation fails fast with an actionable
    message instead of an opaque subprocess error when the dependency is
    missing from the environment.
    """
    if shutil.which("manim-slides") is not None:
        return None
    if _module_available("manim_slides"):
        return None
    return (
        "manim-slides is not installed in the current environment. "
        "Install it with 'pip install manim-slides' to render or compile "
        "presentations."
    )


def _validate_python_syntax(code: str) -> str | None:
    """Return a clear error message for invalid Python code, or None.

    Pre-validates user-provided code so syntax errors fail fast (before any
    subprocess is spawned) with a precise line number and message.
    """
    try:
        ast.parse(code)
    except SyntaxError as exc:
        lineno = exc.lineno or "?"
        return f"SyntaxError at line {lineno}: {exc.msg}"
    except (ValueError, TypeError) as exc:
        return f"Invalid Python code: {exc}"
    return None


_MODULE_NOT_FOUND_RE = re.compile(
    r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"
)


def _extract_missing_module(stderr: str) -> str | None:
    """Return the name of a missing Python module from stderr, or None.

    Detects ``ModuleNotFoundError`` traces produced when user code imports a
    dependency that is not installed, so the tool can surface an actionable
    hint instead of a raw traceback.
    """
    match = _MODULE_NOT_FOUND_RE.search(stderr)
    if match is None:
        return None
    return match.group(1)


def _quote_js_string(val: str) -> str:
    """Ensure a string option is quoted for Reveal.js Jinja template injection."""
    if (val.startswith("'") and val.endswith("'")) or (
        val.startswith('"') and val.endswith('"')
    ):
        return val
    return f"'{val}'"


def _build_convert_command(
    scenes: list[str],
    dest: str,
    folder: str = "slides",
    output_format: str = "auto",
    config: dict[str, str] | None = None,
    one_file: bool = False,
) -> list[str]:
    """Build the argument list for ``manim-slides convert``."""
    command = [*_manim_slides_executable(), "convert"]
    command += ["--folder", folder, "--to", output_format]
    if one_file:
        command.append("--one-file")
    is_html = output_format == "html" or (
        output_format == "auto" and dest.endswith(".html")
    )
    for key, value in (config or {}).items():
        if is_html and key in {
            "transition",
            "transition_speed",
            "navigation_mode",
            "background_transition",
        }:
            value = _quote_js_string(value)
        command += ["-c", f"{key}={value}"]
    command += [*scenes, dest]
    return command


REVEAL_THEMES = (
    "black",
    "white",
    "league",
    "beige",
    "sky",
    "night",
    "serif",
    "simple",
    "solarized",
    "blood",
    "moon",
    "dracula",
)

REVEAL_TRANSITIONS = ("none", "fade", "slide", "convex", "concave", "zoom")

REVEAL_TRANSITION_SPEEDS = ("default", "fast", "slow")


def _validate_reveal_options(
    theme: str,
    transition: str,
    transition_speed: str,
) -> str | None:
    """Return an error message for invalid Reveal.js options, or None if valid."""
    if theme not in REVEAL_THEMES:
        return f"Invalid theme '{theme}'. Valid themes: {', '.join(REVEAL_THEMES)}."
    if transition not in REVEAL_TRANSITIONS:
        return (
            f"Invalid transition '{transition}'. "
            f"Valid transitions: {', '.join(REVEAL_TRANSITIONS)}."
        )
    if transition_speed not in REVEAL_TRANSITION_SPEEDS:
        return (
            f"Invalid transition_speed '{transition_speed}'. "
            f"Valid speeds: {', '.join(REVEAL_TRANSITION_SPEEDS)}."
        )
    return None


def _build_reveal_config(
    theme: str = "black",
    transition: str = "none",
    transition_speed: str = "default",
    controls: bool = False,
    progress: bool = False,
    slide_number: bool = False,
    hash: bool = False,
    loop: bool = False,
    title: str | None = None,
    config: dict[str, str] | None = None,
) -> list[str]:
    """Build ``-c key=value`` converter arguments for a Reveal.js HTML deck."""
    values: dict[str, str] = {
        "reveal_theme": theme,
        "transition": _quote_js_string(transition),
        "transition_speed": _quote_js_string(transition_speed),
        "controls": str(controls).lower(),
        "progress": str(progress).lower(),
        "slide_number": str(slide_number).lower(),
        "hash": str(hash).lower(),
        "loop": str(loop).lower(),
    }
    if title:
        values["title"] = title
    for key, value in (config or {}).items():
        if key in {
            "transition",
            "transition_speed",
            "navigation_mode",
            "background_transition",
        }:
            value = _quote_js_string(value)
        values[key] = value
    args: list[str] = []
    for key, value in values.items():
        args += ["-c", f"{key}={value}"]
    return args


def _build_revealjs_export_command(
    scenes: list[str],
    dest: str,
    folder: str = "slides",
    theme: str = "black",
    transition: str = "none",
    transition_speed: str = "default",
    controls: bool = False,
    progress: bool = False,
    slide_number: bool = False,
    hash: bool = False,
    loop: bool = False,
    title: str | None = None,
    config: dict[str, str] | None = None,
    one_file: bool = False,
    offline: bool = False,
) -> list[str]:
    """Build the argument list for a Reveal.js HTML export via convert."""
    command = [*_manim_slides_executable(), "convert"]
    command += ["--folder", folder, "--to", "html"]
    if one_file:
        command.append("--one-file")
    if offline:
        command.append("--offline")
    command += _build_reveal_config(
        theme=theme,
        transition=transition,
        transition_speed=transition_speed,
        controls=controls,
        progress=progress,
        slide_number=slide_number,
        hash=hash,
        loop=loop,
        title=title,
        config=config,
    )
    command += [*scenes, dest]
    return command


def _run_convert(
    command: list[str],
    dest: str,
    scenes: list[str],
    output_format: str,
    cwd: str | None,
    timeout: int,
) -> str:
    """Run a ``manim-slides convert`` command and return a structured JSON result."""
    availability_error = _manim_slides_availability_error()
    if availability_error:
        return json.dumps({"success": False, "error": availability_error})
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        destination = Path(cwd or ".").joinpath(dest).resolve()
        output = {
            "success": result.returncode == 0,
            "format": output_format,
            "destination": str(destination),
            "scenes": scenes,
            "command": command,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
        if result.returncode != 0:
            output["error"] = result.stderr.strip() or "Unknown conversion error."
        return json.dumps(output, indent=2)
    except subprocess.TimeoutExpired as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Conversion timed out after {timeout}s: {e}",
            }
        )
    except FileNotFoundError as e:
        return json.dumps(
            {
                "success": False,
                "error": f"manim-slides executable not found: {e}",
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Error executing convert tool: {e}",
            }
        )


@mcp.tool()
def compile_presentation(
    scenes: list[str],
    dest: str,
    folder: str = "slides",
    output_format: str = "auto",
    config: dict[str, str] | None = None,
    one_file: bool = False,
    workspace_dir: str | None = None,
    timeout: int = 300,
) -> str:
    """Compile rendered Manim-Slides scenes using ``manim-slides convert``.

    Wraps ``manim-slides convert`` to turn rendered slide assets into an
    interactive presentation (e.g., Reveal.js HTML, PDF, or PPTX).

    Args:
        scenes: Names of the rendered Scene/Slide classes to include, in order.
        dest: Destination path for the compiled presentation
            (e.g., "presentation.html"). The format is inferred from the
            extension when ``output_format`` is "auto".
        folder: Directory containing the rendered slide assets (default "slides").
        output_format: Conversion format: "auto", "html", "pdf", "pptx", or "zip".
        config: Extra converter options as key/value pairs
            (e.g., {"slide_number": "true"}).
        one_file: Embed all local assets (e.g., videos) into a single output file.
        workspace_dir: Working directory for the conversion. Defaults to the
            ``WORKSPACE_DIR`` environment variable or the current directory.
        timeout: Maximum time in seconds to wait for the conversion.

    Returns:
        A JSON string with the conversion status, output destination,
        executed command, and captured stdout/stderr.
    """
    cwd = workspace_dir or os.environ.get("WORKSPACE_DIR")
    command = _build_convert_command(
        scenes=scenes,
        dest=dest,
        folder=folder,
        output_format=output_format,
        config=config,
        one_file=one_file,
    )
    return _run_convert(command, dest, scenes, output_format, cwd, timeout)


@mcp.tool()
def export_revealjs_html(
    scenes: list[str],
    dest: str,
    folder: str = "slides",
    theme: str = "black",
    transition: str = "none",
    transition_speed: str = "default",
    controls: bool = False,
    progress: bool = False,
    slide_number: bool = False,
    hash: bool = False,
    loop: bool = False,
    title: str | None = None,
    config: dict[str, str] | None = None,
    one_file: bool = False,
    offline: bool = False,
    workspace_dir: str | None = None,
    timeout: int = 300,
) -> str:
    """Export rendered Manim-Slides scenes to an interactive Reveal.js HTML deck.

    Wraps ``manim-slides convert --to html`` with first-class Reveal.js
    configuration for themes, transitions, and navigation controls.

    Args:
        scenes: Names of the rendered Scene/Slide classes to include, in order.
        dest: Destination path for the exported HTML deck
            (e.g., "presentation.html").
        folder: Directory containing the rendered slide assets (default "slides").
        theme: Reveal.js theme: "black", "white", "league", "beige", "sky",
            "night", "serif", "simple", "solarized", "blood", "moon", or
            "dracula". Defaults to "black".
        transition: Slide transition: "none", "fade", "slide", "convex",
            "concave", or "zoom". Defaults to "none".
        transition_speed: Transition speed: "default", "fast", or "slow".
        controls: Show navigation control arrows in the corner.
        progress: Show a presentation progress bar.
        slide_number: Display the current slide number.
        hash: Add the current slide to the URL hash for deep linking.
        loop: Loop the presentation.
        title: Presentation title used in the browser tab.
        config: Extra Reveal.js converter options as key/value pairs
            (e.g., {"background_color": "white"}).
        one_file: Embed all local assets (e.g., videos) into a single HTML file.
        offline: Download remote Reveal.js assets for offline viewing.
        workspace_dir: Working directory for the conversion. Defaults to the
            ``WORKSPACE_DIR`` environment variable or the current directory.
        timeout: Maximum time in seconds to wait for the conversion.

    Returns:
        A JSON string with the export status, output destination,
        executed command, and captured stdout/stderr.
    """
    error = _validate_reveal_options(theme, transition, transition_speed)
    if error:
        return json.dumps({"success": False, "error": error})
    cwd = workspace_dir or os.environ.get("WORKSPACE_DIR")
    command = _build_revealjs_export_command(
        scenes=scenes,
        dest=dest,
        folder=folder,
        theme=theme,
        transition=transition,
        transition_speed=transition_speed,
        controls=controls,
        progress=progress,
        slide_number=slide_number,
        hash=hash,
        loop=loop,
        title=title,
        config=config,
        one_file=one_file,
        offline=offline,
    )
    return _run_convert(command, dest, scenes, "html", cwd, timeout)


_PREVIEW_SERVERS: dict[str, ThreadingHTTPServer] = {}
_PREVIEW_SERVERS_LOCK = threading.Lock()


def _preview_server_key(directory: Path) -> str:
    """Return the registry key for a served directory."""
    return str(directory.resolve())


def _start_preview_server(
    directory: Path,
    host: str,
    port: int | None,
) -> tuple[ThreadingHTTPServer, int, bool]:
    """Start a background HTTP server for ``directory``, or reuse an existing one.

    The server runs in a daemon thread for the lifetime of the MCP process.
    When ``port`` is None, an ephemeral OS-assigned port is used. Returns the
    server instance, the bound port, and whether an existing server was reused.
    """
    key = _preview_server_key(directory)
    with _PREVIEW_SERVERS_LOCK:
        existing = _PREVIEW_SERVERS.get(key)
        if existing is not None:
            return existing, existing.server_address[1], True
        handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
        server = ThreadingHTTPServer((host, port or 0), handler)
        server.daemon_threads = True
        _PREVIEW_SERVERS[key] = server

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1], False


@mcp.tool()
def serve_revealjs_html(
    dest: str,
    workspace_dir: str | None = None,
    host: str = "127.0.0.1",
    port: int | None = None,
    open_browser: bool = True,
) -> str:
    """Serve an exported Reveal.js HTML deck on a local HTTP server for preview.

    Starts an ephemeral background HTTP server that serves the workspace so the
    deck's relative slide assets resolve, and returns a URL that can be opened
    in a browser (optionally opening it automatically).

    Args:
        dest: Path to the exported HTML deck (e.g., "presentation.html"). Resolved
            relative to ``workspace_dir`` when not absolute.
        workspace_dir: Working directory. Defaults to the ``WORKSPACE_DIR``
            environment variable or the current directory.
        host: Bind address for the server (default "127.0.0.1").
        port: Port to bind. When None, an ephemeral OS-assigned port is used.
        open_browser: When True, attempt to open the URL in the default browser.

    Returns:
        A JSON string with the preview URL, bound port, served directory, and
        whether an existing server was reused.
    """
    cwd = workspace_dir or os.environ.get("WORKSPACE_DIR") or "."
    workspace = Path(cwd).resolve()
    dest_path = Path(dest)
    if not dest_path.is_absolute():
        dest_path = (workspace / dest_path).resolve()

    if not dest_path.is_file():
        return json.dumps(
            {
                "success": False,
                "error": f"HTML deck not found: {dest_path}",
            }
        )
    if dest_path.suffix.lower() != ".html":
        return json.dumps(
            {
                "success": False,
                "error": f"Expected an .html file, got: {dest_path}",
            }
        )

    try:
        url_path = dest_path.relative_to(workspace).as_posix()
        serve_dir = workspace
    except ValueError:
        url_path = dest_path.name
        serve_dir = dest_path.parent

    try:
        server, bound_port, reused = _start_preview_server(serve_dir, host, port)
    except OSError as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Failed to start preview server: {e}",
            }
        )

    url = f"http://{host}:{bound_port}/{url_path}"

    browser_opened = False
    if open_browser:
        try:
            browser_opened = bool(webbrowser.open(url))
        except Exception:
            browser_opened = False

    return json.dumps(
        {
            "success": True,
            "url": url,
            "host": host,
            "port": bound_port,
            "directory": str(serve_dir.resolve()),
            "file": url_path,
            "reused": reused,
            "browser_opened": browser_opened,
        },
        indent=2,
    )


@mcp.tool()
def stop_preview_server(port: int | None = None) -> str:
    """Stop running ephemeral preview servers started by ``serve_revealjs_html``.

    Args:
        port: Port of the server to stop. When omitted, all preview servers
            started by this MCP process are stopped.

    Returns:
        A JSON string listing the stopped ports and the number of remaining
        active preview servers.
    """
    with _PREVIEW_SERVERS_LOCK:
        if port is None:
            targets = [
                (key, server, server.server_address[1])
                for key, server in _PREVIEW_SERVERS.items()
            ]
            _PREVIEW_SERVERS.clear()
        else:
            targets = [
                (key, server, server.server_address[1])
                for key, server in _PREVIEW_SERVERS.items()
                if server.server_address[1] == port
            ]
            for key, _, _ in targets:
                _PREVIEW_SERVERS.pop(key, None)

    stopped: list[int] = []
    for _, server, bound_port in targets:
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            continue
        stopped.append(bound_port)

    return json.dumps(
        {
            "success": True,
            "stopped_ports": stopped,
            "remaining": len(_PREVIEW_SERVERS),
        },
        indent=2,
    )


PREVIEW_IMAGE_FORMATS = {"png", "jpg", "jpeg", "webp"}
PREVIEW_VIDEO_FORMATS = {"mp4", "gif"}

GIF_FILTER = (
    "fps=15,scale=640:-1:flags=lanczos,"
    "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
)


def _ffmpeg_executable() -> str | None:
    """Return the path to the ffmpeg executable, or None if unavailable."""
    return shutil.which("ffmpeg")


def _ffprobe_duration(path: str | Path) -> float | None:
    """Return the media duration in seconds reported by ffprobe, or None.

    Args:
        path: Path to the media file to probe.

    Returns:
        The duration in seconds, or None when ffprobe is unavailable, the
        probe fails, or the output cannot be parsed as a number.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def _load_scene_config(folder_path: Path, scene: str) -> dict | None:
    """Load a rendered scene's slide configuration from ``folder_path``."""
    config_path = folder_path / f"{scene}.json"
    if not config_path.is_file():
        return None
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _collect_scene_metadata(folder_path: Path) -> list[dict]:
    """Collect slide metadata for every rendered scene config in ``folder_path``."""
    scenes = []
    for json_file in sorted(folder_path.glob("*.json")):
        data = _load_scene_config(folder_path, json_file.stem)
        if data is None:
            continue
        slides = data.get("slides", [])
        scenes.append(
            {
                "scene": json_file.stem,
                "slide_count": len(slides),
                "resolution": data.get("resolution"),
                "background_color": data.get("background_color"),
                "slides": [
                    {
                        "index": index,
                        "type": slide.get("type"),
                        "file": slide.get("file"),
                    }
                    for index, slide in enumerate(slides)
                ],
            }
        )
    return scenes


def _resolve_slide_media(cwd: str | None, slide: dict) -> Path | None:
    """Resolve the media file for a slide relative to the workspace root."""
    file = slide.get("file")
    if not file:
        return None
    return Path(cwd or ".").joinpath(file).resolve()


@mcp.tool()
def list_scenes(folder: str = "slides", workspace_dir: str | None = None) -> str:
    """Discover rendered scenes and their slide metadata in the workspace.

    Reads the slide configuration files (``<scene>.json``) produced by
    ``manim-slides render`` and returns structured metadata for each scene,
    including slide counts, resolution, and per-slide media files.

    Args:
        folder: Directory containing the rendered slide assets (default "slides").
        workspace_dir: Working directory. Defaults to the ``WORKSPACE_DIR``
            environment variable or the current directory.

    Returns:
        A JSON string listing the discovered scenes and their slide metadata.
    """
    cwd = workspace_dir or os.environ.get("WORKSPACE_DIR")
    folder_path = Path(cwd or ".").joinpath(folder)
    if not folder_path.is_dir():
        return json.dumps(
            {
                "success": False,
                "error": f"Slides folder not found: {folder_path}",
            }
        )
    scenes = _collect_scene_metadata(folder_path)
    return json.dumps(
        {
            "success": True,
            "folder": str(folder_path.resolve()),
            "scene_count": len(scenes),
            "scenes": scenes,
        },
        indent=2,
    )


@mcp.tool()
def preview_slide(
    scene: str,
    slide_index: int = 0,
    output_format: str = "png",
    folder: str = "slides",
    workspace_dir: str | None = None,
    timeout: int = 120,
) -> str:
    """Extract a single-slide preview (image or video) without compiling the deck.

    Reads the rendered slide configuration for ``scene`` and produces a preview
    of the slide at ``slide_index``: an image frame (png/jpg/webp), a video
    snippet (mp4), or an animated GIF.

    Args:
        scene: Name of the rendered Scene/Slide class to preview.
        slide_index: Zero-based index of the slide within the scene.
        output_format: Preview format: "png", "jpg", "jpeg", "webp", "mp4",
            or "gif". Defaults to "png".
        folder: Directory containing the rendered slide assets (default "slides").
        workspace_dir: Working directory. Defaults to the ``WORKSPACE_DIR``
            environment variable or the current directory.
        timeout: Maximum time in seconds to wait for ffmpeg preview generation.

    Returns:
        A JSON string with the preview status, output path, and format.
    """
    output_format = output_format.lower()
    supported = sorted(PREVIEW_IMAGE_FORMATS | PREVIEW_VIDEO_FORMATS)
    if output_format not in PREVIEW_IMAGE_FORMATS | PREVIEW_VIDEO_FORMATS:
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"Unsupported output_format '{output_format}'. "
                    f"Valid formats: {', '.join(supported)}."
                ),
            }
        )
    cwd = workspace_dir or os.environ.get("WORKSPACE_DIR")
    folder_path = Path(cwd or ".").joinpath(folder)
    data = _load_scene_config(folder_path, scene)
    if data is None:
        return json.dumps(
            {
                "success": False,
                "error": f"Scene '{scene}' not found in {folder_path}.",
            }
        )
    slides = data.get("slides", [])
    if not 0 <= slide_index < len(slides):
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"Slide index {slide_index} out of range "
                    f"(scene '{scene}' has {len(slides)} slides)."
                ),
            }
        )
    slide = slides[slide_index]
    media = _resolve_slide_media(cwd, slide)
    if media is None or not media.is_file():
        return json.dumps(
            {
                "success": False,
                "error": f"Slide media file not found: {slide.get('file')}",
            }
        )
    slide_type = slide.get("type")
    if slide_type == "image" and output_format in PREVIEW_VIDEO_FORMATS:
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"Cannot preview image slide as '{output_format}'. "
                    "Use an image format (png/jpg/webp) instead."
                ),
            }
        )

    preview_dir = Path(cwd or ".").joinpath("preview")
    preview_dir.mkdir(parents=True, exist_ok=True)
    destination = preview_dir / f"{scene}_{slide_index}.{output_format}"

    command: list[str] | None = None
    if slide_type == "image":
        matches = media.suffix.lower() == f".{output_format}" or (
            output_format == "jpeg" and media.suffix.lower() == ".jpg"
        )
        if not matches:
            command = ["ffmpeg", "-y", "-i", str(media), str(destination)]
    elif output_format == "mp4":
        if media.suffix.lower() != ".mp4":
            command = ["ffmpeg", "-y", "-i", str(media), str(destination)]
    elif output_format == "gif":
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(media),
            "-vf",
            GIF_FILTER,
            str(destination),
        ]
    else:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(media),
            "-vf",
            "thumbnail",
            "-frames:v",
            "1",
            "-update",
            "1",
            str(destination),
        ]

    if command is not None:
        ffmpeg = _ffmpeg_executable()
        if ffmpeg is None:
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        "ffmpeg executable not found. "
                        "Install FFmpeg to generate previews."
                    ),
                }
            )
        command[0] = ffmpeg
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Preview generation timed out after {timeout}s: {e}",
                }
            )
        if result.returncode != 0:
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        result.stderr.strip() or "Unknown preview generation error."
                    ),
                }
            )
    else:
        shutil.copyfile(media, destination)

    return json.dumps(
        {
            "success": True,
            "scene": scene,
            "slide_index": slide_index,
            "slide_type": slide_type,
            "output_format": output_format,
            "preview_path": str(destination.resolve()),
        },
        indent=2,
    )


EXPORT_TRANSITIONS = ("none", "fade")


def _concat_list_text(segments: list[str]) -> str:
    """Return the ffmpeg concat demuxer list-file content for ``segments``.

    Args:
        segments: Segment file paths to concatenate, in playback order.

    Returns:
        The text of a concat demuxer list file with one ``file`` directive
        per segment.
    """
    return "".join(f"file '{segment}'\n" for segment in segments)


def _build_export_command(
    media: list[dict],
    dest: str,
    width: int,
    height: int,
    segment_paths: list[str],
    fps: int = 30,
    transition: str = "none",
    transition_duration: float = 0.5,
    image_duration: float = 2.0,
    concat_list_path: str = "concat.txt",
    durations: list[float] | None = None,
) -> list[list[str]]:
    """Build the ffmpeg command pipeline that exports slides to one video.

    Every slide is normalized to an intermediate segment (libx264, yuv420p,
    shared frame size and rate) with letterbox padding; still-image slides
    become fixed-duration segments via ``-loop 1``. The segments are then
    assembled with the concat demuxer (``transition="none"``) or an xfade
    crossfade chain (``transition="fade"``).

    Args:
        media: Slides to export, in playback order. Each entry is a dict with
            "path" (media file) and "type" ("image" for still-image slides).
        dest: Destination path for the exported video.
        width: Target frame width in pixels.
        height: Target frame height in pixels.
        segment_paths: Output path for each normalized intermediate segment,
            one per entry in ``media``.
        fps: Target frame rate for the normalized segments.
        transition: Assembly mode: "none" (hard cuts) or "fade" (crossfades).
        transition_duration: Duration in seconds of each crossfade.
        image_duration: Duration in seconds for still-image slides.
        concat_list_path: Path of the concat demuxer list file used when
            ``transition`` is "none".
        durations: Duration in seconds of each normalized segment. Required
            to compute xfade offsets when ``transition`` is "fade" and more
            than one segment is exported.

    Returns:
        A list of ffmpeg argument lists: one normalization command per slide
        followed by the final assembly command.

    Raises:
        ValueError: If ``media`` and ``segment_paths`` differ in length or the
            fade offsets cannot be computed from ``durations``.
    """
    if len(media) != len(segment_paths):
        raise ValueError("media and segment_paths must have the same length.")
    normalize_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={fps}"
    )
    commands: list[list[str]] = []
    for slide, segment in zip(media, segment_paths, strict=True):
        command = ["ffmpeg", "-y"]
        if slide.get("type") == "image":
            command += ["-loop", "1", "-t", str(image_duration)]
        command += [
            "-i",
            str(slide["path"]),
            "-vf",
            normalize_filter,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(segment),
        ]
        commands.append(command)

    if transition == "none":
        commands.append(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list_path),
                "-c",
                "copy",
                str(dest),
            ]
        )
        return commands

    inputs: list[str] = []
    for segment in segment_paths:
        inputs += ["-i", str(segment)]
    if len(segment_paths) == 1:
        commands.append(["ffmpeg", "-y", *inputs, "-c", "copy", str(dest)])
        return commands
    if durations is None or len(durations) != len(segment_paths):
        raise ValueError("durations are required to build fade transitions.")
    filters = []
    previous = "[0:v]"
    for index in range(1, len(segment_paths)):
        offset = sum(durations[:index]) - index * transition_duration
        label = f"[x{index}]"
        filters.append(
            f"{previous}[{index}:v]xfade=transition=fade:"
            f"duration={transition_duration}:offset={round(offset, 6)}{label}"
        )
        previous = label
    commands.append(
        [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            previous,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(dest),
        ]
    )
    return commands


@mcp.tool()
def export_video(
    scenes: list[str],
    dest: str = "presentation.mp4",
    folder: str = "slides",
    workspace_dir: str | None = None,
    fps: int = 30,
    width: int | None = None,
    height: int | None = None,
    transition: str = "none",
    transition_duration: float = 0.5,
    image_duration: float = 2.0,
    timeout: int = 600,
) -> str:
    """Concatenate slide media across scenes into a single MP4 video.

    Reads the rendered slide configurations for ``scenes`` and stitches every
    slide into one video with FFmpeg. Each slide is normalized to a common
    frame size and rate (still images become fixed-duration segments) before
    the segments are joined with the concat demuxer (``transition="none"``) or
    an xfade crossfade chain (``transition="fade"``). Intermediates are
    written to a temporary directory and cleaned up automatically.

    Args:
        scenes: Names of the rendered Scene/Slide classes to include, in order.
        dest: Destination path for the exported video
            (e.g., "presentation.mp4").
        folder: Directory containing the rendered slide assets (default "slides").
        workspace_dir: Working directory. Defaults to the ``WORKSPACE_DIR``
            environment variable or the current directory.
        fps: Frame rate of the exported video. Defaults to 30.
        width: Target frame width in pixels. Defaults to the first scene's
            rendered resolution.
        height: Target frame height in pixels. Defaults to the first scene's
            rendered resolution.
        transition: Segment transition: "none" (hard cuts) or "fade"
            (crossfades). Defaults to "none".
        transition_duration: Duration in seconds of each crossfade when
            ``transition`` is "fade". Defaults to 0.5.
        image_duration: Duration in seconds for still-image slides. Defaults
            to 2.0.
        timeout: Maximum time in seconds to wait for the export.

    Returns:
        A JSON string with the export status, destination path, exported
        scenes, slide count, total duration, executed command, and captured
        stdout/stderr.
    """
    if transition not in EXPORT_TRANSITIONS:
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"Invalid transition '{transition}'. "
                    f"Valid transitions: {', '.join(EXPORT_TRANSITIONS)}."
                ),
            }
        )
    if fps < 1:
        return json.dumps(
            {
                "success": False,
                "error": f"fps must be a positive integer, got {fps}.",
            }
        )
    if image_duration <= 0:
        return json.dumps(
            {
                "success": False,
                "error": f"image_duration must be positive, got {image_duration}.",
            }
        )
    if transition_duration < 0:
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"transition_duration must be non-negative, "
                    f"got {transition_duration}."
                ),
            }
        )
    if not scenes:
        return json.dumps({"success": False, "error": "No scenes provided."})

    cwd = workspace_dir or os.environ.get("WORKSPACE_DIR")
    folder_path = Path(cwd or ".").joinpath(folder)

    slides: list[dict] = []
    first_resolution = None
    for scene in scenes:
        data = _load_scene_config(folder_path, scene)
        if data is None:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Scene '{scene}' not found in {folder_path}.",
                }
            )
        if first_resolution is None:
            first_resolution = data.get("resolution")
        for slide in data.get("slides", []):
            slides.append(
                {
                    "path": _resolve_slide_media(cwd, slide),
                    "type": slide.get("type"),
                    "file": slide.get("file"),
                }
            )
    if not slides:
        return json.dumps(
            {
                "success": False,
                "error": f"No slides found in scenes: {', '.join(scenes)}.",
            }
        )

    missing = [
        str(entry["path"] if entry["path"] is not None else entry["file"])
        for entry in slides
        if entry["path"] is None or not entry["path"].is_file()
    ]
    if missing:
        return json.dumps(
            {
                "success": False,
                "error": f"Slide media files not found: {', '.join(missing)}.",
            }
        )

    if width is None or height is None:
        if (
            isinstance(first_resolution, (list, tuple))
            and len(first_resolution) == 2
            and all(isinstance(value, int) and value > 0 for value in first_resolution)
        ):
            width = width if width is not None else first_resolution[0]
            height = height if height is not None else first_resolution[1]
    if width is None or height is None:
        return json.dumps(
            {
                "success": False,
                "error": (
                    "Could not determine target width/height: pass them "
                    "explicitly or render scenes with a valid 'resolution' entry."
                ),
            }
        )
    if width < 1 or height < 1:
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"width and height must be positive integers, "
                    f"got {width}x{height}."
                ),
            }
        )

    ffmpeg = _ffmpeg_executable()
    if ffmpeg is None:
        return json.dumps(
            {
                "success": False,
                "error": (
                    "ffmpeg executable not found. "
                    "Install FFmpeg to export videos."
                ),
            }
        )

    destination = Path(cwd or ".").joinpath(dest).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    media = [
        {"path": str(entry["path"]), "type": entry["type"]} for entry in slides
    ]
    deadline = time.monotonic() + timeout
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="manim_export_") as tmp:
            workdir = Path(tmp)
            segment_paths = [
                str(workdir / f"segment_{index:03d}.mp4")
                for index in range(len(media))
            ]
            concat_list_path = workdir / "concat.txt"
            # Normalization is transition-independent; the fade offsets can
            # only be computed once the segments exist and are measured.
            commands = _build_export_command(
                media=media,
                dest=str(destination),
                width=width,
                height=height,
                segment_paths=segment_paths,
                fps=fps,
                transition="none",
                transition_duration=transition_duration,
                image_duration=image_duration,
                concat_list_path=str(concat_list_path),
            )
            concat_list_path.write_text(
                _concat_list_text(segment_paths), encoding="utf-8"
            )
            for command in commands:
                command[0] = ffmpeg
            for command in commands[:-1]:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=max(0.001, deadline - time.monotonic()),
                )
                if result.stdout.strip():
                    stdout_parts.append(result.stdout.strip())
                if result.stderr.strip():
                    stderr_parts.append(result.stderr.strip())
                if result.returncode != 0:
                    return json.dumps(
                        {
                            "success": False,
                            "error": (
                                result.stderr.strip()
                                or "Unknown video export error."
                            ),
                            "stdout": result.stdout.strip(),
                            "stderr": result.stderr.strip(),
                        },
                        indent=2,
                    )

            durations = [_ffprobe_duration(segment) for segment in segment_paths]
            if any(duration is None for duration in durations):
                return json.dumps(
                    {
                        "success": False,
                        "error": (
                            "Could not determine slide segment durations "
                            "with ffprobe."
                        ),
                    }
                )
            if transition == "fade":
                commands = _build_export_command(
                    media=media,
                    dest=str(destination),
                    width=width,
                    height=height,
                    segment_paths=segment_paths,
                    fps=fps,
                    transition=transition,
                    transition_duration=transition_duration,
                    image_duration=image_duration,
                    concat_list_path=str(concat_list_path),
                    durations=durations,
                )
                commands[-1][0] = ffmpeg
            command = commands[-1]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max(0.001, deadline - time.monotonic()),
            )
            if result.stdout.strip():
                stdout_parts.append(result.stdout.strip())
            if result.stderr.strip():
                stderr_parts.append(result.stderr.strip())
            if result.returncode != 0:
                return json.dumps(
                    {
                        "success": False,
                        "error": (
                            result.stderr.strip() or "Unknown video export error."
                        ),
                        "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip(),
                    },
                    indent=2,
                )
        segment_durations = [duration for duration in durations if duration is not None]
        if transition == "fade" and len(segment_durations) > 1:
            total_duration = sum(segment_durations) - (
                len(segment_durations) - 1
            ) * transition_duration
        else:
            total_duration = sum(segment_durations)
        return json.dumps(
            {
                "success": True,
                "dest": str(destination),
                "scenes": scenes,
                "slide_count": len(slides),
                "transition": transition,
                "duration": round(total_duration, 3),
                "command": command,
                "stdout": "\n".join(stdout_parts),
                "stderr": "\n".join(stderr_parts),
            },
            indent=2,
        )
    except subprocess.TimeoutExpired as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Video export timed out after {timeout}s: {e}",
            }
        )
    except FileNotFoundError as e:
        return json.dumps(
            {
                "success": False,
                "error": f"ffmpeg executable not found: {e}",
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Error executing export_video tool: {e}",
            }
        )


MEDIA_EXTENSIONS = {".mp4", ".webm", ".mov", ".gif", ".png", ".jpg", ".jpeg"}

CACHE_DIR_NAME = ".render_cache"

CACHEABLE_EXTENSIONS = MEDIA_EXTENSIONS | {".json"}


def _resolve_workspace_dir(media_dir: str | None = None) -> Path:
    """Resolve and create the directory used to store rendered media."""
    if media_dir:
        workspace = Path(media_dir)
    elif os.environ.get("WORKSPACE_DIR"):
        workspace = Path(os.environ["WORKSPACE_DIR"])
    else:
        workspace = Path(tempfile.gettempdir()) / "manim_slides_mcp"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


@contextmanager
def _temporary_script(code: str, directory: Path) -> Iterator[Path]:
    """Write ``code`` to a secure temporary ``.py`` file and clean it up after."""
    fd, raw_path = tempfile.mkstemp(
        suffix=".py",
        prefix="manim_",
        dir=str(directory),
    )
    path = Path(raw_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(code)
        yield path
    finally:
        path.unlink(missing_ok=True)


def _build_render_command(
    script: Path,
    scenes: list[str] | None,
    quality: str,
    media_dir: Path,
) -> list[str]:
    """Build the argument list for ``manim-slides render``."""
    command = [
        *_manim_slides_executable(),
        "render",
        "-q",
        quality,
        "--media_dir",
        str(media_dir),
    ]
    if scenes:
        command += [str(script), *scenes]
    else:
        command += ["-a", str(script)]
    return command


def _find_media_files(media_dir: Path, since: float) -> list[str]:
    """Return media files created or modified in ``media_dir`` since ``since``."""
    return sorted(
        str(path)
        for path in media_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in MEDIA_EXTENSIONS
        and "partial_movie_files" not in path.parts
        and CACHE_DIR_NAME not in path.parts
        and path.stat().st_mtime >= since - 1
    )


def _render_cache_key(code: str, scenes: list[str] | None, quality: str) -> str:
    """Return a deterministic content hash for a render request.

    The key captures the source code, the requested scene subset, and the
    render quality, so unchanged requests map to the same cache entry.
    """
    payload = json.dumps(
        {"code": code, "scenes": scenes, "quality": quality},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _render_cache_entry(workspace: Path, key: str) -> Path:
    """Return the cache directory for a given render key."""
    return workspace / CACHE_DIR_NAME / key


def _find_rendered_outputs(workspace: Path, since: float) -> list[str]:
    """Return render outputs (media + slide configs) created since ``since``."""
    return sorted(
        str(path)
        for path in workspace.rglob("*")
        if path.is_file()
        and path.suffix.lower() in CACHEABLE_EXTENSIONS
        and "partial_movie_files" not in path.parts
        and CACHE_DIR_NAME not in path.parts
        and path.stat().st_mtime >= since - 1
    )


def _save_render_cache(workspace: Path, key: str, files: list[str]) -> Path:
    """Copy rendered files into the content-addressed cache and write a manifest."""
    entry = _render_cache_entry(workspace, key)
    entry.mkdir(parents=True, exist_ok=True)
    relative_files: list[str] = []
    for raw_path in files:
        source = Path(raw_path)
        relative = source.relative_to(workspace)
        destination = entry / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        relative_files.append(str(relative))
    (entry / "manifest.json").write_text(
        json.dumps({"key": key, "files": relative_files}, indent=2),
        encoding="utf-8",
    )
    return entry


def _load_render_cache(workspace: Path, key: str) -> list[str] | None:
    """Return cached relative file paths for ``key``, or None on a miss.

    A cache entry is only considered valid when its manifest exists and every
    recorded file is still present on disk.
    """
    entry = _render_cache_entry(workspace, key)
    manifest = entry / "manifest.json"
    if not manifest.is_file():
        return None
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        files = data.get("files")
        if not isinstance(files, list):
            return None
    except (json.JSONDecodeError, OSError):
        return None
    if any(not (entry / rel).is_file() for rel in files):
        return None
    return files


def _restore_render_cache(
    workspace: Path,
    key: str,
    files: list[str],
) -> list[str]:
    """Copy cached files back into the workspace and return their absolute paths."""
    entry = _render_cache_entry(workspace, key)
    restored: list[str] = []
    for relative in files:
        source = entry / relative
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        restored.append(str(destination.resolve()))
    return restored


@dataclass(frozen=True)
class RenderProgress:
    """A parsed render-progress update extracted from manim's tqdm output."""

    percent: float
    current: int | None
    total: int | None
    description: str


_RENDER_PROGRESS_RE = re.compile(
    r"(?P<desc>.*?)\s*(?P<percent>\d{1,3})\s*%\s*\|"
    r".*\|"
    r"\s*(?P<current>\d+)/(?P<total>\d+|\?)\s*\["
)


def _parse_render_progress(line: str) -> RenderProgress | None:
    """Parse a tqdm-style progress line into a ``RenderProgress`` update.

    Manim (and manim-slides) report rendering progress through ``tqdm`` bars on
    stderr, e.g. ``Animation 0: FadeIn(Circle):  50%|█████     | 1/2 [...]``.
    Returns ``None`` for lines that do not contain a progress bar.
    """
    match = _RENDER_PROGRESS_RE.search(line)
    if match is None:
        return None
    percent = float(match.group("percent"))
    current = int(match.group("current"))
    total_raw = match.group("total")
    total = None if total_raw == "?" else int(total_raw)
    description = match.group("desc").strip().rstrip(":").strip()
    return RenderProgress(
        percent=percent,
        current=current,
        total=total,
        description=description,
    )


def _format_progress_message(progress: RenderProgress) -> str:
    """Render a ``RenderProgress`` update into a human-readable message."""
    label = progress.description or "Rendering"
    if progress.total is not None:
        frames = f"{progress.current}/{progress.total} frames"
    else:
        frames = f"{progress.current} frames"
    return f"{label}: {frames} ({progress.percent:.0f}%)"


async def _report_render_progress(
    ctx: Context | None,
    progress: float,
    total: float,
    message: str,
) -> None:
    """Send a ``notifications/progress`` update to the client when available.

    Best-effort by design: a no-op when the tool was invoked without an MCP
    request context (e.g. a direct function call or unit test) or when the
    client did not request progress tracking for this request.
    """
    if ctx is None:
        return
    try:
        await ctx.report_progress(progress, total, message)
    except (AttributeError, ValueError):
        pass


async def _read_stream(stream: asyncio.StreamReader) -> str:
    """Read an async byte stream to completion and return its decoded text."""
    chunks: list[bytes] = []
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


async def _pump_progress_stream(
    stream: asyncio.StreamReader,
    on_segment: Callable[[str], Awaitable[None]],
) -> str:
    """Read ``stream``, emit ``\\r``/``\\n``-delimited segments, return full text.

    tqdm updates in place using carriage returns rather than newlines, so we
    split the raw stream on both separators to stream each progress update as
    soon as it is written while still reconstructing the full captured text.
    """
    raw: list[bytes] = []
    buffer = b""
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            break
        raw.append(chunk)
        buffer += chunk
        while True:
            cr = buffer.find(b"\r")
            lf = buffer.find(b"\n")
            if cr == -1 and lf == -1:
                break
            sep = lf if cr == -1 else (cr if lf == -1 else min(cr, lf))
            segment = buffer[:sep]
            buffer = buffer[sep + 1 :]
            if segment.strip():
                await on_segment(segment.decode("utf-8", errors="replace"))
    if buffer.strip():
        await on_segment(buffer.decode("utf-8", errors="replace"))
    return b"".join(raw).decode("utf-8", errors="replace")


def _kill_process_tree(process: asyncio.subprocess.Process) -> None:
    """Terminate a subprocess and its children.

    Manim/ffmpeg spawn child processes, so killing only the direct child can
    leave orphans that keep holding the workspace lock. On POSIX we kill the
    whole process group; elsewhere we fall back to killing the child directly.
    """
    if os.name == "posix":
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass
    process.kill()


async def _run_render_streaming(
    command: list[str],
    workspace: Path,
    scenes: list[str] | None,
    quality: str,
    start: float,
    timeout: int,
    ctx: Context | None,
) -> dict:
    """Run ``manim-slides render`` and stream frame progress to the client."""
    await _report_render_progress(ctx, 0.0, 100.0, "Starting render...")
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=workspace,
        start_new_session=True,
    )

    async def on_segment(segment: str) -> None:
        progress = _parse_render_progress(segment)
        if progress is None:
            return
        await _report_render_progress(
            ctx,
            progress.percent,
            100.0,
            _format_progress_message(progress),
        )

    stdout_task = asyncio.create_task(_read_stream(process.stdout))
    stderr_task = asyncio.create_task(_pump_progress_stream(process.stderr, on_segment))

    try:
        returncode = await asyncio.wait_for(process.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        _kill_process_tree(process)
        await process.wait()
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
        await _report_render_progress(ctx, 100.0, 100.0, "Render timed out.")
        raise subprocess.TimeoutExpired(command, timeout) from None

    stdout_text = await stdout_task
    stderr_text = await stderr_task

    media_files = _find_media_files(workspace, start)
    output = {
        "success": returncode == 0,
        "scenes": scenes or ["(all)"],
        "quality": quality,
        "media_dir": str(workspace.resolve()),
        "media_files": media_files,
        "command": command,
        "stdout": stdout_text.strip(),
        "stderr": stderr_text.strip(),
    }
    if returncode != 0:
        output["error"] = stderr_text.strip() or "Unknown render error."
        missing_module = _extract_missing_module(stderr_text)
        if missing_module:
            output["missing_dependency"] = missing_module
            output["hint"] = (
                f"The Python module '{missing_module}' is not installed. "
                f"Install it with 'pip install {missing_module}'."
            )
    await _report_render_progress(ctx, 100.0, 100.0, "Render complete.")
    return output


@mcp.tool()
async def execute_manim_code(
    code: str,
    scenes: list[str] | None = None,
    quality: str = "l",
    media_dir: str | None = None,
    timeout: int = 600,
    use_cache: bool = True,
    ctx: Context | None = None,
) -> str:
    """Execute Manim-Slides Python code and render the resulting scenes.

    Writes the provided code to a secure temporary script, renders it with
    ``manim-slides render`` (headless, no preview popup), and returns the
    produced media files. Rendered-frame percentages are streamed to the client
    as ``notifications/progress`` updates while rendering is in progress.

    Renders are cached by a content hash of ``code``, ``scenes``, and
    ``quality``: an unchanged request reuses the previously rendered media
    instead of re-rendering.

    Args:
        code: Python source code defining one or more Manim Scene/Slide classes.
        scenes: Names of the Scene/Slide classes to render. If omitted or empty,
            all scenes in the file are rendered.
        quality: Render quality: "l" (low), "m" (medium), "h" (high),
            "p" (2K), or "k" (4K). Defaults to "l".
        media_dir: Directory where rendered media is stored. Defaults to the
            ``WORKSPACE_DIR`` environment variable or a temporary directory.
        timeout: Maximum time in seconds to wait for rendering.
        use_cache: When True, reuse previously rendered media for unchanged
            requests instead of re-rendering. Defaults to True.

    Returns:
        A JSON string with the render status, produced media file paths,
        executed command, and captured stdout/stderr. A cache hit sets
        ``cached`` to True and omits the command.
    """
    workspace = _resolve_workspace_dir(media_dir)

    syntax_error = _validate_python_syntax(code)
    if syntax_error:
        return json.dumps({"success": False, "error": syntax_error})

    availability_error = _manim_slides_availability_error()
    if availability_error:
        return json.dumps({"success": False, "error": availability_error})

    if use_cache:
        key = _render_cache_key(code, scenes, quality)
        cached_files = _load_render_cache(workspace, key)
        if cached_files is not None:
            restored = _restore_render_cache(workspace, key, cached_files)
            media_files = [
                path
                for path in restored
                if Path(path).suffix.lower() in MEDIA_EXTENSIONS
            ]
            await _report_render_progress(ctx, 100.0, 100.0, "Render skipped (cached).")
            return json.dumps(
                {
                    "success": True,
                    "cached": True,
                    "scenes": scenes or ["(all)"],
                    "quality": quality,
                    "media_dir": str(workspace.resolve()),
                    "media_files": media_files,
                    "stdout": "",
                    "stderr": "",
                },
                indent=2,
            )

    start = time.time()
    try:
        with _temporary_script(code, workspace) as script:
            command = _build_render_command(
                script=script,
                scenes=scenes,
                quality=quality,
                media_dir=workspace,
            )
            result = await _run_render_streaming(
                command=command,
                workspace=workspace,
                scenes=scenes,
                quality=quality,
                start=start,
                timeout=timeout,
                ctx=ctx,
            )
        if use_cache and result.get("success"):
            try:
                _save_render_cache(
                    workspace,
                    _render_cache_key(code, scenes, quality),
                    _find_rendered_outputs(workspace, start),
                )
            except OSError:
                pass
        return json.dumps(result, indent=2)
    except subprocess.TimeoutExpired as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Rendering timed out after {timeout}s: {e}",
            }
        )
    except FileNotFoundError as e:
        return json.dumps(
            {
                "success": False,
                "error": f"manim-slides executable not found: {e}",
            }
        )
    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": f"Error executing execute_manim_code tool: {e}",
            }
        )


def main() -> None:
    """Run the Manim-Slides MCP server.

    Transport is selected via ``--transport`` (default ``stdio`` for local
    AI desktop clients). Use ``--transport streamable-http`` to expose the
    server over HTTP for remote clients (e.g. Claude.ai via a public tunnel).
    """
    parser = argparse.ArgumentParser(description="Manim-Slides MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for HTTP transports (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port for HTTP transports (default: 8000)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
