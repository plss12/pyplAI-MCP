"""End to end over stdio: any stray print on stdout would corrupt the protocol and fail these calls."""

import sys

import pytest
from mcp import Client, StdioServerParameters


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_stdio_server_plays_and_analyses():
    params = StdioServerParameters(command=sys.executable, args=["-m", "pyplai_mcp"])
    async with Client(params) as client:
        assert client.server_info is not None and client.server_info.name == "pyplai"
        state = (await client.call_tool("new_game", {"game": "ultimate", "opponent": "mcts", "opponent_seconds": 0.1})).structured_content
        analysis = await client.call_tool("analyze_position", {"game_id": state["game_id"], "seconds": 0.2})
        assert not analysis.is_error
        result = await client.call_tool("play_move", {"game_id": state["game_id"], "move": analysis.structured_content["best_move"]})
        assert not result.is_error
        assert result.structured_content["state"]["status"] == "your_turn"
