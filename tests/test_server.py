import re

import pytest
from mcp import Client

from pyplai_mcp.server import mcp


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        yield c


async def call(client, tool, **args):
    result = await client.call_tool(tool, args)
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def call_error(client, tool, **args):
    result = await client.call_tool(tool, args)
    assert result.is_error
    return result.content[0].text


@pytest.mark.anyio
async def test_lists_tools_resources_and_prompts(client):
    tools = {t.name for t in (await client.list_tools()).tools}
    assert tools == {"list_games", "new_game", "get_state", "play_move", "analyze_position", "end_game"}
    games = (await call(client, "list_games"))["result"]
    assert [g["name"] for g in games] == ["tictactoe", "ultimate", "phantom"]
    phantom = games[2]
    assert "mcts" not in phantom["opponents"] and "mo-ismcts" in phantom["analysis_algorithms"]
    rules = await client.read_resource("rules://ultimate")
    assert "closed board" in rules.contents[0].text
    prompt = await client.get_prompt("play_game", {"game": "phantom"})
    assert "analyze_position" in prompt.messages[0].content.text


@pytest.mark.anyio
async def test_full_game_against_random_opponent(client):
    state = await call(client, "new_game", game="tictactoe", opponent="random", seed=1)
    assert state["status"] == "your_turn" and len(state["legal_moves"]) == 9
    while state["status"] == "your_turn":
        result = await call(client, "play_move", game_id=state["game_id"], move=state["legal_moves"][0])
        state = result["state"]
    assert state["status"] in ("you_won", "you_lost", "draw")
    assert state["legal_moves"] == []
    assert await call_error(client, "play_move", game_id=state["game_id"], move="a1")


@pytest.mark.anyio
async def test_opponent_moves_first_when_you_play_second(client):
    state = await call(client, "new_game", game="ultimate", play_as=2, opponent="random", seed=2)
    assert state["history"][0].startswith("Your opponent (random) played")
    assert state["board"].count("X") == 1


@pytest.mark.anyio
async def test_illegal_move_lists_the_legal_ones(client):
    state = await call(client, "new_game", game="tictactoe", opening=["b2"], opponent="random")
    message = await call_error(client, "play_move", game_id=state["game_id"], move="b2")
    assert "not a legal move" in message and "a1" in message


@pytest.mark.anyio
async def test_unknown_game_id_and_invalid_arguments(client):
    assert "No game with id" in await call_error(client, "get_state", game_id="nope")
    assert await call_error(client, "analyze_position", game_id="nope", seconds=99)
    message = await call_error(client, "new_game", game="phantom", opponent="mcts")
    assert "not available for phantom" in message


@pytest.mark.anyio
@pytest.mark.parametrize("algorithm", ["mcts", "minimax"])
async def test_analysis_finds_the_winning_move(client, algorithm):
    # X has a1 and b1; c1 wins at once
    state = await call(client, "new_game", game="tictactoe", opening=["a1", "a2", "b1", "b2"], opponent="random")
    analysis = await call(client, "analyze_position", game_id=state["game_id"], algorithm=algorithm, seconds=0.5, top_k=3)
    assert analysis["best_move"] == "c1"
    assert analysis["moves"][0]["move"] == "c1" and len(analysis["moves"]) == 3
    assert analysis["metric"] == ("minimax_score" if algorithm == "minimax" else "win_rate")


@pytest.mark.anyio
async def test_opening_sets_up_a_position_and_rejects_bad_moves(client):
    state = await call(client, "new_game", game="tictactoe", opening=["a1", "b2"], opponent="random")
    assert state["board"].splitlines()[1] == "1 X . ."
    assert "Opening move 2" in await call_error(client, "new_game", game="tictactoe", opening=["a1", "a1"])


@pytest.mark.anyio
async def test_end_game_forgets_the_session(client):
    state = await call(client, "new_game", game="tictactoe", opponent="random")
    assert (await call(client, "end_game", game_id=state["game_id"]))["removed"]
    assert "No game with id" in await call_error(client, "get_state", game_id=state["game_id"])


@pytest.mark.anyio
async def test_phantom_never_reveals_hidden_stones(client):
    """Everything the player receives during a Phantom game must be consistent with what they know."""
    from pyplai_mcp.server import store

    state = await call(client, "new_game", game="phantom", opponent="mo-ismcts", opponent_seconds=0.05, seed=4)
    game_id = state["game_id"]
    game = store.get(game_id).game
    for _ in range(30):
        if state["status"] != "your_turn":
            break
        hidden = {game.move_id(i) for i, v in enumerate(game.board) if v == 2 and i not in game.discovered[1]}
        # The board shows only your stones and the ones you discovered
        assert state["board"].count("o") == len(game.discovered[1])
        analysis = await call(client, "analyze_position", game_id=game_id, seconds=0.1, top_k=16)
        # Hidden stones are still legal targets, so legality and the analysis say nothing about them
        assert hidden <= set(state["legal_moves"])
        assert {m["move"] for m in analysis["moves"]} <= set(state["legal_moves"])
        for cell in hidden:
            # A hidden cell may only appear as one of your legal moves, never in the history or notes
            assert not re.search(rf"\b{cell}\b", " ".join(state["history"] + state["notes"]))
        result = await call(client, "play_move", game_id=game_id, move=analysis["best_move"])
        state = result["state"]
    else:
        pytest.fail("the game did not end")
    if state["status"] != "your_turn":
        assert any("full board" in note for note in state["notes"])
