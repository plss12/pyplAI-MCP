"""The benchmark harness, with fake models instead of Ollama."""

import re
import sys
from pathlib import Path

import pytest
from mcp import Client

from pyplai_mcp.server import mcp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
from agent import play_game, to_ollama_tools  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


def legal_moves(messages):
    """Legal moves listed in the last user message."""
    text = next(m["content"] for m in reversed(messages) if m["role"] == "user")
    return re.search(r"legal moves: (.*)$", text, re.MULTILINE).group(1).split(", ")


def first_legal(model, messages, tools):
    return {"content": "", "tool_calls": [("play_move", {"move": legal_moves(messages)[0]})], "prompt_tokens": 10, "output_tokens": 2}


def analyse_then_follow(model, messages, tools):
    last = messages[-1]
    if last["role"] == "tool":
        import json

        return {"content": "", "tool_calls": [("play_move", {"move": json.loads(last["content"])["best_move"]})], "prompt_tokens": 10, "output_tokens": 2}
    return {"content": "", "tool_calls": [("analyze_position", {})], "prompt_tokens": 10, "output_tokens": 2}


def chatty(model, messages, tools):
    return {"content": "I think b2 is nice.", "tool_calls": [], "prompt_tokens": 10, "output_tokens": 5}


def illegal_then_legal(model, messages, tools):
    if messages[-1]["role"] == "tool":
        return first_legal(model, messages, tools)
    return {"content": "", "tool_calls": [("play_move", {"move": "z9"})], "prompt_tokens": 10, "output_tokens": 2}


async def tools_for(client):
    return (await client.list_tools()).tools


@pytest.mark.anyio
async def test_tools_hide_game_id_and_search_settings():
    async with Client(mcp) as client:
        tools = to_ollama_tools(await tools_for(client), ["analyze_position", "play_move"])
    by_name = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
    assert set(by_name) == {"analyze_position", "play_move"}
    assert "game_id" not in by_name["play_move"]["properties"] and by_name["play_move"]["required"] == ["move"]
    assert by_name["analyze_position"]["properties"] == {}


@pytest.mark.anyio
@pytest.mark.parametrize("condition, chat", [("llm", first_legal), ("llm+search", analyse_then_follow), ("search", None), ("random", None)])
async def test_every_condition_finishes_a_game(condition, chat):
    async with Client(mcp) as client:
        result, stats = await play_game(
            client, game="tictactoe", condition=condition, model="fake", seed=1, opponent="random",
            opponent_seconds=0.05, analysis_seconds=0.1, chat=chat or first_legal, mcp_tools=await tools_for(client), rules="",
        )
    assert result in ("win", "draw", "loss") and stats.turns >= 1
    assert stats.illegal_moves == stats.fallback_moves == 0
    if condition == "llm+search":
        assert stats.analyze_calls == stats.turns
    if condition in ("search", "random"):
        assert stats.llm_calls == 0


@pytest.mark.anyio
async def test_counts_illegal_moves_and_falls_back_when_the_model_never_calls_a_tool():
    async with Client(mcp) as client:
        tools = await tools_for(client)
        _, illegal = await play_game(client, game="tictactoe", condition="llm", model="fake", seed=0, opponent="random",
                                     opponent_seconds=0.05, analysis_seconds=0.1, chat=illegal_then_legal, mcp_tools=tools)
        _, silent = await play_game(client, game="tictactoe", condition="llm", model="fake", seed=0, opponent="random",
                                    opponent_seconds=0.05, analysis_seconds=0.1, chat=chatty, mcp_tools=tools)
    assert illegal.illegal_moves == illegal.turns and illegal.fallback_moves == 0
    assert silent.fallback_moves == silent.turns and silent.replies_without_tool == 6 * silent.turns
