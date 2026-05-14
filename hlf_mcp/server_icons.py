"""Shared emoji SVG icon helper for MCP tool registrations."""

from mcp.types import Icon


def _emoji_icon(emoji: str) -> Icon:
    """Create a simple emoji SVG icon for MCP tool metadata."""
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="80">{emoji}</text></svg>'
    return Icon(
        src=f"data:image/svg+xml,{svg}",
        mimeType="image/svg+xml",
        sizes=["48x48"],
    )
