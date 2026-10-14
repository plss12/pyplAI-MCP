"""Summarise results.csv: win, draw and loss rates per game, condition and model, with 95% Wilson intervals.

uv run python benchmarks/summary.py [results.csv]
"""

from __future__ import annotations

import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - margin), min(1.0, centre + margin)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("results.csv")
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            groups[(row["game"], row["condition"], row["model"])].append(row)
    print(
        "| Game | Player | Model | Games | Wins [95% CI] | Draws | Losses | Illegal moves / game | Fallback moves / game | Seconds / game |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for (game, condition, model), rows in groups.items():
        n = len(rows)
        wins = sum(r["result"] == "win" for r in rows)
        draws = sum(r["result"] == "draw" for r in rows)
        low, high = wilson(wins, n)
        illegal = statistics.mean(int(r["illegal_moves"]) for r in rows)
        fallback = statistics.mean(int(r["fallback_moves"]) for r in rows)
        seconds = statistics.mean(float(r["seconds"]) for r in rows)
        print(
            f"| {game} | {condition} | {model} | {n} | {100 * wins / n:.0f}% [{100 * low:.0f}-{100 * high:.0f}] | "
            f"{100 * draws / n:.0f}% | {100 * (n - wins - draws) / n:.0f}% | {illegal:.2f} | {fallback:.2f} | {seconds:.0f} |"
        )


if __name__ == "__main__":
    main()
