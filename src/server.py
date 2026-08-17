"""Manim-Slides Model Context Protocol (MCP) Server.

Provides tools for AI agents to generate, execute, and compile
interactive presentations using Manim Community and Manim-Slides.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
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


PREVIEW_IMAGE_FORMATS = {"png", "jpg", "jpeg", "webp"}
PREVIEW_VIDEO_FORMATS = {"mp4", "gif"}

GIF_FILTER = (
    "fps=15,scale=640:-1:flags=lanczos,"
    "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
)


def _ffmpeg_executable() -> str | None:
    """Return the path to the ffmpeg executable, or None if unavailable."""
    return shutil.which("ffmpeg")


def _load_scene_config(folder_path: Path, scene: str) -> dict | None:
    """Load a rendered scene's slide configuration from ``folder_path``."""
    config_path = folder_path / f"{scene}.json"
    if not config_path.is_file():
        return None
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


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
        pass
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
        process.kill()
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
    """Run the Manim-Slides MCP server using stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
