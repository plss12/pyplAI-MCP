"""pyplAI search engines for each game."""

from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, Protocol

import pyplAI

from .games import Game

EngineName = Literal["random", "mcts", "minimax", "so-ismcts", "mo-ismcts"]

# Perfect-information algorithms would see the hidden stones in Phantom, so each game lists the
# algorithms that are fair to use on it
PERFECT_INFORMATION: tuple[EngineName, ...] = ("mcts", "minimax", "random")
IMPERFECT_INFORMATION: tuple[EngineName, ...] = ("mo-ismcts", "so-ismcts", "random")


def engines_for(game: type[Game]) -> tuple[EngineName, ...]:
    return PERFECT_INFORMATION if game.perfect_information else IMPERFECT_INFORMATION


def default_analysis_engine(game: type[Game]) -> EngineName:
    return "mcts" if game.perfect_information else "mo-ismcts"


@dataclass
class Evaluation:
    move: int
    visits: int
    value: float


@dataclass
class SearchResult:
    best: int
    moves: list[Evaluation]
    iterations: int
    seconds: float


class Engine(Protocol):
    def analiza(self, estado: Game, /) -> pyplAI.ResultadoAnalisis: ...


class RandomEngine:
    """Picks a legal move uniformly at random."""

    def __init__(self, seed: int | None) -> None:
        self.rng = random.Random(seed)

    def analiza(self, estado: Game) -> pyplAI.ResultadoAnalisis:
        moves = estado.legal_moves()
        move = self.rng.choice(moves)
        return pyplAI.ResultadoAnalisis(move, [pyplAI.EvaluacionMovimiento(m, 0, 0.0) for m in moves])


def build(game: type[Game], name: EngineName, *, seconds: float = 1.0, depth: int = 3, seed: int | None = None) -> Engine:
    if name not in engines_for(game):
        raise ValueError(f"{name} is not available for {game.name}. Choose one of: {', '.join(engines_for(game))}.")
    g = game
    if name == "random":
        return RandomEngine(seed)
    if name == "mcts":
        return pyplAI.MCTS(g.apply, g.legal_moves, g.is_terminal, g.is_winner, 2, seconds, semilla=seed)
    if name == "minimax":
        return pyplAI.Minimax(g.apply, g.legal_moves, g.is_terminal, g.is_winner, g.heuristic, 2, depth)
    if name == "so-ismcts":
        return pyplAI.SOISMCTS(g.apply, g.legal_moves, g.is_terminal, g.is_winner, g.determinize, 2, seconds, semilla=seed)
    return pyplAI.MOISMCTS(g.apply, g.legal_moves, g.is_terminal, g.is_winner, g.determinize, g.is_visible, 2, seconds, semilla=seed)


def search(engine: Engine, state: Game) -> SearchResult:
    """Analyse a copy of state, so the search can never touch the real game."""
    result = engine.analiza(deepcopy(state))
    return SearchResult(
        best=result.movimiento,
        moves=[Evaluation(e.movimiento, e.visitas, e.valor) for e in result.movimientos],
        iterations=result.iteraciones,
        seconds=result.tiempo,
    )
