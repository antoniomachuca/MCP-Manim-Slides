# Manim-Slides MCP Server

A robust Model Context Protocol (MCP) server that empowers AI agents to generate, orchestrate, and compile interactive presentations with manim-slides.

## Overview

While traditional AI coding assistants can write Manim code, executing that code and structuring it into a readable presentation format has remained a manual process. This MCP server bridges the gap by providing AI clients (like Claude Desktop, Cursor, or Antigravity) with direct tools to:

1. **Execute Manim Scripts**: Dynamically run generated Manim code safely.
2. **Handle Slides Orchestration**: Natively support the `Slide` class for presentation logic.
3. **Compile Presentations**: Convert rendered animations into interactive HTML presentations (Reveal.js) directly from the AI prompt.

## Features

- **Direct Code Execution**: Send Python code containing Manim `Slide` classes; the server handles temporary file creation, execution, and cleanup.
- **Error Feedback Loop**: Captures standard output and runtime exceptions, feeding them back to the AI for autonomous debugging.
- **Live Render Progress**: Streams rendered-frame percentage updates to the client via `notifications/progress`.
- **Render Caching**: Content-hashes each render request (code + scenes + quality) to skip re-rendering unchanged slides, reusing previously rendered media from `.render_cache`.
- **HTML/Reveal.js Export**: Seamlessly compiles the generated video assets into a fully functional interactive web presentation.
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
```

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
- `execute_manim_code(code: str, scenes: list[str] | None = None, quality: str = "l", media_dir: str | None = None, timeout: int = 600, use_cache: bool = True)`: Writes the provided Manim code to a secure temporary script, renders the scenes headlessly via `manim-slides render`, and returns paths to produced media files. Caches rendered output by a content hash of `code`/`scenes`/`quality` and skips re-rendering unchanged requests unless `use_cache=False`.
- `compile_presentation(scenes: list[str], dest: str, folder: str = "slides", output_format: str = "auto", config: dict[str, str] | None = None, one_file: bool = False, workspace_dir: str | None = None, timeout: int = 300)`: Compiles rendered slide assets into an interactive presentation via `manim-slides convert` (supports `html`/Reveal.js, `pdf`, `pptx`, `zip`, custom Reveal.js themes and transition configs).
- `export_revealjs_html(scenes: list[str], dest: str, folder: str = "slides", theme: str = "black", transition: str = "none", transition_speed: str = "default", controls: bool = False, progress: bool = False, slide_number: bool = False, hash: bool = False, loop: bool = False, title: str | None = None, config: dict[str, str] | None = None, one_file: bool = False, offline: bool = False, workspace_dir: str | None = None, timeout: int = 300)`: First-class Reveal.js HTML export via `manim-slides convert --to html`, with typed configuration for themes, transitions, navigation controls, slide numbers, deep linking, looping, and offline/one-file embedding.
- `preview_slide(scene: str, slide_index: int = 0, output_format: str = "png", folder: str = "slides", workspace_dir: str | None = None, timeout: int = 120)`: Extracts a single slide preview (image frame `png`/`jpg`/`webp`, video snippet `mp4`, or animated `gif`) via FFmpeg for rapid visual validation without compiling the full presentation.
- `list_scenes(folder: str = "slides", workspace_dir: str | None = None)`: Discovers and lists all rendered scenes, slide counts, and metadata available in the workspace.
- `serve_revealjs_html(dest: str, workspace_dir: str | None = None, host: str = "127.0.0.1", port: int | None = None, open_browser: bool = True)`: Serves an exported Reveal.js HTML deck on an ephemeral local HTTP server for one-click browser preview. Returns the preview URL and optionally opens it in the default browser.
- `stop_preview_server(port: int | None = None)`: Stops a running ephemeral preview server by port, or all preview servers when no port is given.

### Resources (`@mcp.resource`)
- `status://server`: Telemetry resource returning current server status, Python version, and environment details.
- `revealjs://config`: Lists supported Reveal.js HTML export options (themes, transitions, transition speeds, boolean toggles, and defaults).
- `slides://list`: Resource listing all rendered slide configurations and metadata in the active workspace.

## Example Slide Code

```python
from manim import *
from manim_slides import Slide

class IntroPresentation(Slide):
    def construct(self):
        title = Text("Interactive Presentation", font_size=48, color=BLUE)
        self.play(Write(title))
        self.next_slide()  # Slide transition pause

        subtitle = Text("Powered by Manim & MCP", font_size=32).next_to(title, DOWN)
        self.play(FadeIn(subtitle))
        self.next_slide()

        self.play(FadeOut(title), FadeOut(subtitle))
        circle = Circle(radius=2, color=GREEN)
        self.play(Create(circle))
```

## License

This project is licensed under the MIT License.
