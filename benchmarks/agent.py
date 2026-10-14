"""Players for the benchmark: a local LLM (with or without the search tool), pyplAI's search and random play.

Every player talks to the real pyplai-mcp server through an MCP client session, so the benchmark
exercises the same tools an assistant such as Claude would use.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mcp import Client

# Tools the LLM sees in each condition. The harness injects game_id, so the model only chooses moves.
LLM_TOOLS = {"llm": ["play_move"], "llm+search": ["analyze_position", "play_move"]}
CONDITIONS = ["llm", "llm+search", "search", "random"]
# Attempts the model gets per turn before the harness plays a random legal move for it
MAX_STEPS_PER_TURN = 6
OLLAMA_ATTEMPTS = 5
# Deterministic replies, capped in length: a tool call takes under 100 tokens, but a small model
# sometimes falls into a loop of text that runs for minutes. A cut reply counts as one failed attempt.
OLLAMA_OPTIONS = {"temperature": 0, "seed": 0, "num_predict": 512}


@dataclass
class Stats:
    """What happened in one game, from the benchmarked player's side."""

    turns: int = 0
    illegal_moves: int = 0
    replies_without_tool: int = 0
    fallback_moves: int = 0
    analyze_calls: int = 0
    # Turns the model played a move of its own after analysing, and how many of those were the search's best move
    analysed_moves: int = 0
    followed_analysis: int = 0
    llm_calls: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0
    llm_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


# chat(model, messages, tools) -> {"content": str, "tool_calls": [(name, arguments)], "prompt_tokens": int, "output_tokens": int}
ChatFn = Callable[[str, list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]


def ollama_chat(model: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
    """One chat turn with a local Ollama model, deterministic and without long reasoning."""
    import ollama

    # Ollama on Windows sometimes fails to reach its own model runner for a moment. With temperature 0
    # a retry gives the same reply, so retrying does not change the results.
    for attempt in range(1, OLLAMA_ATTEMPTS + 1):
        try:
            response = ollama.chat(model=model, messages=messages, tools=tools, think=False, options=OLLAMA_OPTIONS)
            break
        except (ollama.ResponseError, ConnectionError):
            if attempt == OLLAMA_ATTEMPTS:
                raise
            time.sleep(5 * attempt)
    calls = [(c.function.name, dict(c.function.arguments)) for c in (response.message.tool_calls or [])]
    return {
        "content": response.message.content or "",
        "tool_calls": calls,
        "prompt_tokens": response.prompt_eval_count or 0,
        "output_tokens": response.eval_count or 0,
    }


def to_ollama_tools(mcp_tools: list[Any], names: list[str]) -> list[dict[str, Any]]:
    """MCP tool definitions in Ollama's format, without the game_id argument the harness fills in."""
    tools = []
    for tool in mcp_tools:
        if tool.name not in names:
            continue
        schema = json.loads(json.dumps(tool.input_schema))
        schema.get("properties", {}).pop("game_id", None)
        schema["required"] = [r for r in schema.get("required", []) if r != "game_id"]
        if tool.name == "analyze_position":
            # The harness fixes the search settings so every game gets the same budget
            schema["properties"] = {}
            schema["required"] = []
        tools.append({"type": "function", "function": {"name": tool.name, "description": tool.description or "", "parameters": schema}})
    return tools


def system_prompt(rules: str, condition: str) -> str:
    text = (
        "You are playing a board game against a computer opponent. Here are the rules:\n\n"
        f"{rules}\n\n"
        "Each turn you receive the board as you see it and your legal moves. Choose one and call play_move "
        "with exactly one of the legal moves, written as listed. Do not reply with text instead of a tool call."
    )
    if condition == "llm+search":
        text += (
            " Before moving you can call analyze_position: it runs a search from your position and ranks your legal "
            "moves by the share of simulated games they win. Use it to choose a strong move."
        )
    return text


def describe(state: dict[str, Any]) -> str:
    history = state["history"][-6:]
    return (
        f"Board:\n{state['board']}\n\n"
        + "\n".join(state["notes"])
        + ("\n\nRecent events:\n" + "\n".join(history) if history else "")
        + f"\n\nYour legal moves: {', '.join(state['legal_moves'])}"
    )


async def call(client: Client, tool: str, **arguments: Any) -> tuple[bool, Any]:
    """Call an MCP tool. Returns (ok, structured result or error text)."""
    result = await client.call_tool(tool, arguments)
    if result.is_error:
        return False, result.content[0].text if result.content else "error"
    return True, result.structured_content


async def play_llm_turn(
    client: Client,
    game_id: str,
    state: dict[str, Any],
    model: str,
    condition: str,
    tools: list[dict[str, Any]],
    rules: str,
    chat: ChatFn,
    analysis_seconds: float,
    stats: Stats,
    rng: random.Random,
) -> dict[str, Any]:
    """Let the model choose and play one move. Returns the new state."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt(rules, condition)},
        {"role": "user", "content": describe(state)},
    ]
    best_move = None
    for _ in range(MAX_STEPS_PER_TURN):
        t0 = time.perf_counter()
        reply = chat(model, messages, tools)
        stats.llm_seconds += time.perf_counter() - t0
        stats.llm_calls += 1
        stats.prompt_tokens += reply["prompt_tokens"]
        stats.output_tokens += reply["output_tokens"]
        calls = reply["tool_calls"]
        messages.append(
            {"role": "assistant", "content": reply["content"], "tool_calls": [{"function": {"name": n, "arguments": a}} for n, a in calls]}
        )
        if not calls:
            stats.replies_without_tool += 1
            messages.append({"role": "user", "content": "Call play_move with one of your legal moves: " + ", ".join(state["legal_moves"])})
            continue
        for name, arguments in calls:
            if name == "analyze_position" and condition == "llm+search":
                stats.analyze_calls += 1
                ok, analysis = await call(client, "analyze_position", game_id=game_id, seconds=analysis_seconds, top_k=5)
                if ok:
                    best_move = analysis["best_move"]
                messages.append({"role": "tool", "tool_name": name, "content": json.dumps(analysis) if ok else str(analysis)})
            elif name == "play_move":
                ok, result = await call(client, "play_move", game_id=game_id, move=str(arguments.get("move", "")))
                if ok:
                    if best_move is not None:
                        stats.analysed_moves += 1
                        stats.followed_analysis += result["your_move"] == best_move
                    return result["state"]
                stats.illegal_moves += 1
                messages.append({"role": "tool", "tool_name": name, "content": str(result)})
            else:
                messages.append({"role": "tool", "tool_name": name, "content": f"Unknown tool {name}. Use play_move."})
    # The model never produced a legal move: play a random one so the game can go on, and record it
    stats.fallback_moves += 1
    ok, result = await call(client, "play_move", game_id=game_id, move=rng.choice(state["legal_moves"]))
    if not ok:
        raise RuntimeError(result)
    return result["state"]


async def play_game(
    client: Client,
    *,
    game: str,
    condition: str,
    model: str,
    seed: int,
    opponent: str,
    opponent_seconds: float,
    analysis_seconds: float,
    chat: ChatFn = ollama_chat,
    mcp_tools: list[Any] | None = None,
    rules: str = "",
) -> tuple[str, Stats]:
    """Play one full game. Returns ("win" | "draw" | "loss", stats)."""
    rng = random.Random(seed)
    stats = Stats()
    play_as = 1 + seed % 2  # alternate who moves first
    ok, state = await call(client, "new_game", game=game, play_as=play_as, opponent=opponent, opponent_seconds=opponent_seconds, seed=seed)
    if not ok:
        raise RuntimeError(state)
    game_id = state["game_id"]
    tools = to_ollama_tools(mcp_tools or [], LLM_TOOLS.get(condition, []))
    try:
        while state["status"] == "your_turn":
            stats.turns += 1
            if condition == "random":
                ok, result = await call(client, "play_move", game_id=game_id, move=rng.choice(state["legal_moves"]))
                state = result["state"]
            elif condition == "search":
                ok, analysis = await call(client, "analyze_position", game_id=game_id, seconds=analysis_seconds, top_k=1)
                ok, result = await call(client, "play_move", game_id=game_id, move=analysis["best_move"])
                state = result["state"]
            else:
                state = await play_llm_turn(client, game_id, state, model, condition, tools, rules, chat, analysis_seconds, stats, rng)
    finally:
        await call(client, "end_game", game_id=game_id)
    outcome = {"you_won": "win", "you_lost": "loss", "draw": "draw"}[state["status"]]
    return outcome, stats
