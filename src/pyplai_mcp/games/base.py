"""Common interface for the board games exposed by the server.

Every game is a mutable state object that pyplAI can search directly: the algorithms receive
the unbound methods (``Game.legal_moves``, ``Game.apply``...) and read ``jugadorActual``, the
attribute pyplAI uses for the player to move.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from typing import ClassVar, Self

Move = int


class Game(ABC):
    """A two-player game state compatible with pyplAI."""

    name: ClassVar[str]
    title: ClassVar[str]
    summary: ClassVar[str]
    perfect_information: ClassVar[bool]
    move_format: ClassVar[str]
    rules: ClassVar[str]

    # Player to move (1 or 2). pyplAI requires this exact attribute name.
    jugadorActual: int

    def __init__(self) -> None:
        self.jugadorActual = 1

    @property
    def current_player(self) -> int:
        return self.jugadorActual

    @abstractmethod
    def legal_moves(self) -> list[Move]:
        """Moves available to the player to move, in a fixed order. Empty when the game is over."""

    @abstractmethod
    def apply(self, move: Move) -> Self:
        """Apply a legal move in place and return the state."""

    @abstractmethod
    def is_winner(self, player: int) -> bool:
        """Whether player has won."""

    def is_terminal(self) -> bool:
        return self.is_winner(1) or self.is_winner(2) or not self.legal_moves()

    def winner(self) -> int | None:
        """1 or 2 when the game is won, 0 for a draw and None while it is in progress."""
        for player in (1, 2):
            if self.is_winner(player):
                return player
        return 0 if self.is_terminal() else None

    def heuristic(self, player: int) -> float:
        """Evaluation used by Minimax at its depth limit. Higher is better for player."""
        return 0.0

    def determinize(self) -> Self:
        """A state sampled from what the player to move knows. Perfect-information games return a copy."""
        return deepcopy(self)

    @staticmethod
    def is_visible(move: Move) -> bool:
        """Whether the opponent sees a move (used by MO-ISMCTS)."""
        return True

    @abstractmethod
    def move_id(self, move: Move) -> str:
        """Stable, human-readable identifier of a move, such as ``b2``."""

    def parse_move(self, text: str) -> Move:
        """Inverse of move_id. Raises ValueError for text that is not a legal move."""
        wanted = text.strip()
        for move in self.legal_moves():
            if self.move_id(move).lower() == wanted.lower():
                return move
        raise ValueError(wanted)

    @abstractmethod
    def render(self, viewer: int) -> str:
        """Text board as seen by viewer. Must not reveal information hidden from viewer."""

    def notes(self, viewer: int) -> list[str]:
        """Extra facts about the position that viewer is allowed to know."""
        return []


def columns(n: int) -> str:
    return "abcdefghijklmnopqrstuvwxyz"[:n]


def find_lines(size: int, length: int) -> list[tuple[int, ...]]:
    """Every straight line of length cells on a size x size board, as flat indexes."""
    lines = []
    for r in range(size):
        for c in range(size):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = [(r + k * dr, c + k * dc) for k in range(length)]
                if all(0 <= rr < size and 0 <= cc < size for rr, cc in cells):
                    lines.append(tuple(rr * size + cc for rr, cc in cells))
    return lines
