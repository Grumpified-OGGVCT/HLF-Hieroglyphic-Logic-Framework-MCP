"""HLF MCP package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hlf-mcp")
except PackageNotFoundError:
    __version__ = "0.5.0"

__all__ = ["__version__"]
