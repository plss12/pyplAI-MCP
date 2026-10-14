"""MCP server that exposes pyplAI's game-search algorithms as tools for language models."""

from __future__ import annotations

import argparse
import logging
import sys
from importlib.metadata import version

__version__ = version("pyplai-mcp")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pyplai-mcp", description=__doc__)
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="Host for streamable-http.")
    parser.add_argument("--port", type=int, default=8000, help="Port for streamable-http.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    # Over stdio, stdout carries the protocol, so logs always go to stderr
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from .server import mcp

    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
