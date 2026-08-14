"""Smoke tests to verify project structure and environment dependencies."""

import importlib


def test_mcp_import():
    """Verify MCP SDK v2 is installed and MCPServer is importable."""
    mcp_server = importlib.import_module("mcp.server")
    assert hasattr(mcp_server, "MCPServer"), "MCPServer should be in mcp.server"


def test_manim_import():
    """Verify Manim Community library is installed."""
    manim = importlib.import_module("manim")
    assert hasattr(manim, "Scene")
    assert hasattr(manim, "Circle")


def test_manim_slides_import():
    """Verify Manim-Slides is installed and Slide class is available."""
    manim_slides = importlib.import_module("manim_slides")
    assert hasattr(manim_slides, "Slide")


def test_package_structure():
    """Verify src package can be imported."""
    src = importlib.import_module("src")
    assert src is not None
