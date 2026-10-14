"""Benchmark: how much do local LLMs improve at board games when they can call pyplAI's search?

Plays full games through the pyplai-mcp server (spawned over stdio) and appends one CSV row per
game. Runs can be stopped and resumed: games already in the CSV are skipped.

    uv run --group bench python benchmarks/run.py
    uv run --group bench python benchmarks/run.py --games tictactoe --per-game 2   # quick pilot
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import time
from pathlib import Path

from mcp import Client, StdioServerParameters

from agent import CONDITIONS, play_game

COLUMNS = [
    "game", "condition", "model", "opponent", "seed", "play_as", "result", "turns", "illegal_moves",
    "replies_without_tool", "fallback_moves", "analyze_calls", "llm_calls", "prompt_tokens",
    "output_tokens", "llm_seconds", "seconds",
]
# Opponent of each game: the strongest fair pyplAI algorithm, with a short thinking time
OPPONENTS = {"tictactoe": "mcts", "ultimate": "mcts", "phantom": "mo-ismcts"}
DEFAULT_GAMES_PER_CONFIG = {"tictactoe": 30, "ultimate": 10, "phantom": 20}


def done_keys(path: Path) -> set[tuple[str, str, str, int]]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as f:
        return {(r["game"], r["condition"], r["model"], int(r["seed"])) for r in csv.DictReader(f)}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=["llama3.2:3b"])
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=CONDITIONS)
    parser.add_argument("--games", nargs="+", choices=list(OPPONENTS), default=list(OPPONENTS))
    parser.add_argument("--per-game", type=int, default=0, help="Games per configuration (0 = defaults per game).")
    parser.add_argument("--opponent-seconds", type=float, default=0.2)
    parser.add_argument("--analysis-seconds", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("results.csv"))
    args = parser.parse_args()

    done = done_keys(args.output)
    new_file = not args.output.exists()
    server = StdioServerParameters(command=sys.executable, args=["-m", "pyplai_mcp"])
    async with Client(server) as client:
        mcp_tools = (await client.list_tools()).tools
        with args.output.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, COLUMNS, lineterminator="\n")
            if new_file:
                writer.writeheader()
            for game in args.games:
                rules = (await client.read_resource(f"rules://{game}")).contents[0].text
                games = args.per_game or DEFAULT_GAMES_PER_CONFIG[game]
                for condition in args.conditions:
                    # Search and random play do not use a model, so they run once
                    models = args.models if condition.startswith("llm") else ["-"]
                    for model in models:
                        for seed in range(games):
                            if (game, condition, model, seed) in done:
                                continue
                            t0 = time.perf_counter()
                            result, stats = await play_game(
                                client, game=game, condition=condition, model=model, seed=seed, opponent=OPPONENTS[game],
                                opponent_seconds=args.opponent_seconds, analysis_seconds=args.analysis_seconds,
                                mcp_tools=mcp_tools, rules=rules,
                            )
                            row = {
                                "game": game, "condition": condition, "model": model, "opponent": OPPONENTS[game],
                                "seed": seed, "play_as": 1 + seed % 2, "result": result, "turns": stats.turns,
                                "illegal_moves": stats.illegal_moves, "replies_without_tool": stats.replies_without_tool,
                                "fallback_moves": stats.fallback_moves, "analyze_calls": stats.analyze_calls,
                                "llm_calls": stats.llm_calls, "prompt_tokens": stats.prompt_tokens,
                                "output_tokens": stats.output_tokens, "llm_seconds": round(stats.llm_seconds, 1),
                                "seconds": round(time.perf_counter() - t0, 1),
                            }
                            writer.writerow(row)
                            f.flush()
                            print(f"{game} {condition} {model} seed={seed}: {result} ({row['seconds']} s, "
                                  f"{stats.illegal_moves} illegal, {stats.fallback_moves} fallback)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
