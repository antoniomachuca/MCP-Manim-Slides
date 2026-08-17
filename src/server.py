"""Manim-Slides Model Context Protocol (MCP) Server.

Provides tools for AI agents to generate, execute, and compile
interactive presentations using Manim Community and Manim-Slides.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from mcp.server import MCPServer

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
        return (
            f"Invalid theme '{theme}'. "
            f"Valid themes: {', '.join(REVEAL_THEMES)}."
        )
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


MEDIA_EXTENSIONS = {".mp4", ".webm", ".mov", ".gif", ".png", ".jpg", ".jpeg"}


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
        and path.stat().st_mtime >= since - 1
    )


@mcp.tool()
def execute_manim_code(
    code: str,
    scenes: list[str] | None = None,
    quality: str = "l",
    media_dir: str | None = None,
    timeout: int = 600,
) -> str:
    """Execute Manim-Slides Python code and render the resulting scenes.

    Writes the provided code to a secure temporary script, renders it with
    ``manim-slides render`` (headless, no preview popup), and returns the
    produced media files.

    Args:
        code: Python source code defining one or more Manim Scene/Slide classes.
        scenes: Names of the Scene/Slide classes to render. If omitted or empty,
            all scenes in the file are rendered.
        quality: Render quality: "l" (low), "m" (medium), "h" (high),
            "p" (2K), or "k" (4K). Defaults to "l".
        media_dir: Directory where rendered media is stored. Defaults to the
            ``WORKSPACE_DIR`` environment variable or a temporary directory.
        timeout: Maximum time in seconds to wait for rendering.

    Returns:
        A JSON string with the render status, produced media file paths,
        executed command, and captured stdout/stderr.
    """
    workspace = _resolve_workspace_dir(media_dir)
    start = time.time()
    try:
        with _temporary_script(code, workspace) as script:
            command = _build_render_command(
                script=script,
                scenes=scenes,
                quality=quality,
                media_dir=workspace,
            )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=workspace,
                timeout=timeout,
            )
            media_files = _find_media_files(workspace, start)
            output = {
                "success": result.returncode == 0,
                "scenes": scenes or ["(all)"],
                "quality": quality,
                "media_dir": str(workspace.resolve()),
                "media_files": media_files,
                "command": command,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            }
            if result.returncode != 0:
                output["error"] = result.stderr.strip() or "Unknown render error."
            return json.dumps(output, indent=2)
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
    """Run the Manim-Slides MCP server using stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
