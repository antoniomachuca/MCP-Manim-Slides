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
- **HTML/Reveal.js Export**: Seamlessly compiles the generated video assets into a fully functional interactive web presentation.
- **State Management**: Persists generated media in structured workspace directories for easy access.

## Prerequisites

Ensure your system has the following installed:

- Python 3.10+
- [Manim Community Edition](https://docs.manim.community/en/stable/installation.html) (Requires FFmpeg and LaTeX)
- [Manim-Slides](https://manim-slides.eertmans.be/latest/installation/)

## Installation

```bash
git clone https://github.com/yourusername/mcp-manim-slides.git
cd mcp-manim-slides

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

To integrate this server with an MCP-compatible client (e.g., Claude Desktop), add the following to your client configuration JSON:

```json
{
  "mcpServers": {
    "manim-slides-server": {
      "command": "/absolute/path/to/mcp-manim-slides/.venv/bin/python",
      "args": [
        "/absolute/path/to/mcp-manim-slides/src/server.py"
      ],
      "env": {
        "WORKSPACE_DIR": "/path/to/your/output/directory"
      }
    }
  }
}
```

## Available MCP Tools

- `render_slide(code: str, slide_name: str)`: Executes the provided Manim code and renders the specific slide.
- `compile_presentation(slide_name: str, format: str)`: Compiles the generated slide assets into the specified format (e.g., `html`).
- `get_presentation_status()`: Retrieves the status of the current working directory and existing slide assets.

## License

This project is licensed under the MIT License.
