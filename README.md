# Manim-Slides MCP Server
<div align="center">

[![MCP-Manim-Slides MCP server](https://glama.ai/mcp/servers/antoniomachuca/MCP-Manim-Slides/badges/score.svg)](https://glama.ai/mcp/servers/antoniomachuca/MCP-Manim-Slides)
[![Release](https://img.shields.io/github/v/release/antoniomachuca/MCP-Manim-Slides?style=flat&color=3B82F6)](https://github.com/antoniomachuca/MCP-Manim-Slides/releases)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![CI](https://img.shields.io/github/actions/workflow/status/antoniomachuca/MCP-Manim-Slides/ci.yml?branch=main&label=CI&style=flat)](https://github.com/antoniomachuca/MCP-Manim-Slides/actions)


</div>
A robust Model Context Protocol (MCP) server that empowers AI agents to generate, orchestrate, and compile interactive presentations with manim-slides.

## Overview

While traditional AI coding assistants can write Manim code, executing that code and structuring it into a readable presentation format has remained a manual process. This MCP server bridges the gap by providing AI clients (like Claude Desktop, Cursor, or Antigravity) with direct tools to:

1. **Execute Manim Scripts**: Dynamically run generated Manim code safely.
2. **Handle Slides Orchestration**: Natively support the `Slide` class for presentation logic.
3. **Compile Presentations**: Convert rendered animations into interactive HTML presentations (Reveal.js) directly from the AI prompt.

## Demo

![Manim-Slides MCP Demo](assets/demo.gif)

## Features

- **Direct Code Execution**: Send Python code containing Manim `Slide` classes; the server handles temporary file creation, execution, and cleanup.
- **Error Feedback Loop**: Captures standard output and runtime exceptions, feeding them back to the AI for autonomous debugging.
- **Live Render Progress**: Streams rendered-frame percentage updates to the client via `notifications/progress`.
- **Slide-Archetype Prompt Templates**: Built-in MCP prompts (`title_slide`, `agenda`, `code_walkthrough`, `math_derivation`, `two_column_comparison`) that turn a few arguments into detailed instructions for writing well-laid-out Manim-Slides code.
- **Per-Scene Render Caching**: Content-hashes each scene class (preamble + class source + quality) so editing one scene never re-renders its siblings, reusing previously rendered media from `.render_cache`.
- **Incremental Deck Sync**: `sync_deck` renders only new or changed scenes, restores the rest from cache, reports removed scenes, and recompiles the deck in one call.
- **HTML/Reveal.js Export**: Seamlessly compiles the generated video assets into a fully functional interactive web presentation.
- **Single-MP4 Export**: `export_video` stitches all slide media into one MP4 via FFmpeg, with optional crossfade transitions and fixed-duration handling for still-image slides.
- **Deck Screenshots & Contact Sheets**: `screenshot_deck` captures every slide headlessly (optional Playwright `vision` extra) so the AI can see its own deck, and `contact_sheet` montages slide frames into a single grid image using FFmpeg only.
- **One-Click Browser Preview**: Serves the exported Reveal.js HTML on an ephemeral local HTTP server so it can be opened in a browser with a single call.
- **State Management**: Persists generated media in structured workspace directories for easy access.

## Prerequisites

Ensure your system has the following installed:

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (dependency and environment management)
- [Manim Community Edition](https://docs.manim.community/en/stable/installation.html) (Requires FFmpeg and LaTeX)
- [Manim-Slides](https://manim-slides.eertmans.be/latest/installation.html)

## Installation

```bash
git clone https://github.com/antoniomachuca/MCP-Manim-Slides.git
cd MCP-Manim-Slides

# Install uv if needed: https://docs.astral.sh/uv/getting-started/installation/

# Create the environment and install the project plus dev dependencies
uv sync --extra dev

# Optional: enable deck screenshots (screenshot_deck) via the vision extra
uv sync --extra dev --extra vision
playwright install chromium
```

The `vision` extra (or `pip install "mcp-manim-slides[vision]"` for pip users) adds [Playwright](https://playwright.dev/python/), which `screenshot_deck` needs to capture deck slides headlessly; run `playwright install chromium` once afterwards to download the browser binary. Every other tool — rendering, caching, syncing, compiling, exporting video, and contact sheets — works without it.

## Configuration

To integrate this server with an MCP-compatible client (e.g., Claude Desktop, Cursor, Antigravity), add the following to your client configuration JSON:

```json
{
  "mcpServers": {
    "manim-slides": {
      "command": "/absolute/path/to/MCP-Manim-Slides/.venv/bin/python",
      "args": [
        "/absolute/path/to/MCP-Manim-Slides/mcp_manim_slides/server.py"
      ],
      "env": {
        "WORKSPACE_DIR": "/path/to/your/output/directory"
      }
    }
  }
}
```

## Available MCP Tools & Resources

### Tools (`@mcp.tool`)
- `hello_world(name: str = "World")`: Connectivity check tool to verify client-server MCP communication.
- `execute_manim_code(code: str, scenes: list[str] | None = None, quality: str = "l", media_dir: str | None = None, timeout: int = 600, use_cache: bool = True)`: Writes the provided Manim code to a secure temporary script, renders the scenes headlessly via `manim-slides render`, and returns paths to produced media files. Caches rendered output per scene by a content hash of the shared preamble, the scene class source, and `quality`, so editing one scene never invalidates its siblings; only changed scenes are re-rendered unless `use_cache=False`.
- `sync_deck(code: str, scenes: list[str] | None = None, dest: str = "deck.html", folder: str = "slides", quality: str = "l", output_format: str = "auto", config: dict[str, str] | None = None, one_file: bool = False, media_dir: str | None = None, workspace_dir: str | None = None, timeout: int = 600)`: Renders changed scenes and recompiles the deck in a single call. Compares per-scene content hashes against the render cache and the last successful sync state, renders only new or changed scenes, restores unchanged ones from cache, reports removed scenes, then recompiles the presentation with `manim-slides convert`.
- `compile_presentation(scenes: list[str], dest: str, folder: str = "slides", output_format: str = "auto", config: dict[str, str] | None = None, one_file: bool = False, workspace_dir: str | None = None, timeout: int = 300)`: Compiles rendered slide assets into an interactive presentation via `manim-slides convert` (supports `html`/Reveal.js, `pdf`, `pptx`, `zip`, custom Reveal.js themes and transition configs).
- `export_revealjs_html(scenes: list[str], dest: str, folder: str = "slides", theme: str = "black", transition: str = "none", transition_speed: str = "default", controls: bool = False, progress: bool = False, slide_number: bool = False, hash: bool = False, loop: bool = False, title: str | None = None, config: dict[str, str] | None = None, one_file: bool = False, offline: bool = False, workspace_dir: str | None = None, timeout: int = 300)`: First-class Reveal.js HTML export via `manim-slides convert --to html`, with typed configuration for themes, transitions, navigation controls, slide numbers, deep linking, looping, and offline/one-file embedding.
- `export_video(scenes: list[str], dest: str = "presentation.mp4", folder: str = "slides", workspace_dir: str | None = None, fps: int = 30, width: int | None = None, height: int | None = None, transition: str = "none", transition_duration: float = 0.5, image_duration: float = 2.0, timeout: int = 600)`: Concatenates slide media across scenes into a single MP4 video with FFmpeg. Each slide is normalized to a common frame size and rate (still images become fixed-duration segments) and joined with the concat demuxer (`transition="none"`) or an xfade crossfade chain (`transition="fade"`).
- `preview_slide(scene: str, slide_index: int = 0, output_format: str = "png", folder: str = "slides", workspace_dir: str | None = None, timeout: int = 120)`: Extracts a single slide preview (image frame `png`/`jpg`/`webp`, video snippet `mp4`, or animated `gif`) via FFmpeg for rapid visual validation without compiling the full presentation.
- `screenshot_deck(dest: str, workspace_dir: str | None = None, slides: list[int] | None = None, output_dir: str = "screenshots", width: int = 1920, height: int = 1080, output_format: str = "png", timeout: int = 120)`: Captures screenshots of an exported Reveal.js deck's slides headlessly via Playwright (optional `vision` extra), so an AI agent can "see" its own deck. Serves the deck directory on the local HTTP server and saves one image per slide.
- `contact_sheet(scenes: list[str] | None = None, dest: str = "contact_sheet.png", folder: str = "slides", workspace_dir: str | None = None, columns: int = 3, tile_width: int = 640, timeout: int = 300)`: Composes a grid contact sheet of slide frames using FFmpeg only — one representative frame per slide, montaged into a single image (black filler tiles complete the last row) — so an entire deck can be reviewed at a glance without a browser.
- `list_scenes(folder: str = "slides", workspace_dir: str | None = None)`: Discovers and lists all rendered scenes, slide counts, and metadata available in the workspace.
- `serve_revealjs_html(dest: str, workspace_dir: str | None = None, host: str = "127.0.0.1", port: int | None = None, open_browser: bool = True)`: Serves an exported Reveal.js HTML deck on an ephemeral local HTTP server for one-click browser preview. Returns the preview URL and optionally opens it in the default browser.
- `stop_preview_server(port: int | None = None)`: Stops a running ephemeral preview server by port, or all preview servers when no port is given.

### Resources (`@mcp.resource`)
- `status://server`: Telemetry resource returning current server status, Python version, and environment details.
- `revealjs://config`: Lists supported Reveal.js HTML export options (themes, transitions, transition speeds, boolean toggles, and defaults).
- `slides://list`: Resource listing all rendered slide configurations and metadata in the active workspace.

## Prompts (`@mcp.prompt`)

Slide-archetype prompt templates that expand a few arguments into complete instructions (content, layout guidance, typography, slide mechanics, and a suggested code skeleton) for generating Manim-Slides code:

- `title_slide(title: str, subtitle: str = "", author: str = "")`: Opening title slide with a dominant title and optional subtitle and author lines.
- `agenda(topics: str)`: Agenda slide listing the presentation topics as a numbered list; `topics` is a comma-separated string (e.g. `"Intro, Demo, Results"`).
- `code_walkthrough(code: str, title: str = "")`: Narrates a real code snippet step-by-step across several slides; `code` is embedded verbatim and `title` is an optional heading.
- `math_derivation(steps: str, title: str = "")`: Reveals a math derivation one step per slide; `steps` is a comma-separated list of LaTeX steps (e.g. `"f(x) = x^2, f'(x) = 2x"`).
- `two_column_comparison(left_title: str, right_title: str, left_points: str, right_points: str)`: Side-by-side comparison slide with two titled columns; points are comma-separated strings.

## License

This project is licensed under the MIT License.
