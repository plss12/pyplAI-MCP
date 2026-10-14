"""Phantom (4,4,4): four in a row on a 4x4 board where you cannot see your opponent's stones."""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Self

from .base import Game, Move, columns, find_lines

LINES = find_lines(4, 4)


class Phantom(Game):
    name = "phantom"
    title = "Phantom (4,4,4)"
    summary = "Four in a row on a 4x4 board where the opponent's stones are hidden. Imperfect information."
    perfect_information = False
    move_format = "Column letter and row number, from a1 (top left) to d4 (bottom right)."
    rules = """# Phantom (4,4,4)

Four in a row on a 4x4 board, but you cannot see your opponent's stones (Cowling, Powley and
Whitehouse, 2012). Player 1 moves first.

- On your turn, choose a cell that is not one of your stones and that you have not found to be
  your opponent's.
- If the cell is empty, your stone is placed there and the turn passes.
- If the cell holds a hidden opponent stone, you discover it and must choose again. Your opponent
  is not told.
- The first player with four stones in a row, column or diagonal wins. If no moves are left, the
  game is a draw.

Moves are written as a column letter and a row number: `a1` is the top-left cell and `d4` the
bottom-right one.
"""

    def __init__(self) -> None:
        super().__init__()
        self.board = [0] * 16
        # discovered[p]: opponent stones that player p has found by bumping into them
        self.discovered: dict[int, set[int]] = {1: set(), 2: set()}
        self.stones = {1: 0, 2: 0}
        # Whether the last attempt of the player to move hit a hidden stone
        self.bumped = False

    def legal_moves(self) -> list[Move]:
        if self.is_winner(1) or self.is_winner(2):
            return []
        me = self.jugadorActual
        return [i for i in range(16) if self.board[i] != me and i not in self.discovered[me]]

    def apply(self, move: Move) -> Self:
        me = self.jugadorActual
        if self.board[move] == 0:
            self.board[move] = me
            self.stones[me] += 1
            self.jugadorActual = 3 - me
            self.bumped = False
        else:
            # A hidden opponent stone: the player discovers it and moves again
            self.discovered[me].add(move)
            self.bumped = True
        return self

    def is_winner(self, player: int) -> bool:
        return any(all(self.board[i] == player for i in line) for line in LINES)

    def determinize(self) -> Self:
        """Sample the hidden opponent stones from what the player to move knows.

        The player knows their own stones, the opponent stones they have discovered and how many
        stones the opponent has placed (one per turn). The rest are spread at random over the
        cells the player has not ruled out. The player is not told when the opponent bumps into
        one of their stones, so the opponent's discoveries are forgotten in the sample.
        """
        me, rival = self.jugadorActual, 3 - self.jugadorActual
        sample = deepcopy(self)
        known = self.discovered[me]
        unknown_cells = [i for i in range(16) if self.board[i] != me and i not in known]
        hidden = self.stones[rival] - len(known)
        for i in unknown_cells:
            sample.board[i] = 0
        for i in random.sample(unknown_cells, hidden):
            sample.board[i] = rival
        sample.discovered[rival] = set()
        return sample

    @staticmethod
    def is_visible(move: Move) -> bool:
        return False

    def move_id(self, move: Move) -> str:
        return f"{columns(4)[move % 4]}{move // 4 + 1}"

    def render(self, viewer: int) -> str:
        """You (Y), opponent stones you have discovered (o) and cells you know nothing about (.)."""
        rows = ["  a b c d"]
        for r in range(4):
            cells = []
            for c in range(4):
                i = r * 4 + c
                if self.board[i] == viewer:
                    cells.append("Y")
                elif i in self.discovered[viewer]:
                    cells.append("o")
                else:
                    cells.append(".")
            rows.append(f"{r + 1} " + " ".join(cells))
        return "\n".join(rows)

    def render_full(self) -> str:
        """The whole board, only for finished games."""
        symbols = {0: ".", 1: "1", 2: "2"}
        rows = ["  a b c d"]
        for r in range(4):
            rows.append(f"{r + 1} " + " ".join(symbols[self.board[r * 4 + c]] for c in range(4)))
        return "\n".join(rows)

    def notes(self, viewer: int) -> list[str]:
        rival = 3 - viewer
        hidden = self.stones[rival] - len(self.discovered[viewer])
        notes = [
            "Y is you, o is an opponent stone you have discovered and . is a cell you know nothing about.",
            f"Your opponent has {self.stones[rival]} stones on the board; you have not found {hidden} of them.",
        ]
        if self.bumped and self.jugadorActual == viewer:
            notes.append("Your last attempt hit a hidden opponent stone: it is still your turn.")
        return notes
