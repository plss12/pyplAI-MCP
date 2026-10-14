"""Tic-tac-toe."""

from __future__ import annotations

from typing import Self

from .base import Game, Move, columns, find_lines

LINES = find_lines(3, 3)
SYMBOLS = {0: ".", 1: "X", 2: "O"}


class TicTacToe(Game):
    name = "tictactoe"
    title = "Tic-tac-toe"
    summary = "Three in a row on a 3x3 board. Perfect information."
    perfect_information = True
    move_format = "Column letter and row number, from a1 (top left) to c3 (bottom right)."
    rules = """# Tic-tac-toe

Two players take turns placing their mark on an empty cell of a 3x3 board. Player 1 plays X and
moves first; player 2 plays O. The first to get three marks in a row, column or diagonal wins. If
the board fills up with no line, the game is a draw.

Moves are written as a column letter and a row number: `a1` is the top-left cell and `c3` the
bottom-right one.
"""

    def __init__(self) -> None:
        super().__init__()
        self.board = [0] * 9

    def legal_moves(self) -> list[Move]:
        if self.is_winner(1) or self.is_winner(2):
            return []
        return [i for i in range(9) if self.board[i] == 0]

    def apply(self, move: Move) -> Self:
        self.board[move] = self.jugadorActual
        self.jugadorActual = 3 - self.jugadorActual
        return self

    def is_winner(self, player: int) -> bool:
        return any(all(self.board[i] == player for i in line) for line in LINES)

    def heuristic(self, player: int) -> float:
        # Open lines: two of a kind count 10, one of a kind counts 1
        score = 0.0
        for line in LINES:
            cells = [self.board[i] for i in line]
            if 3 - player not in cells:
                score += {1: 1, 2: 10}.get(cells.count(player), 0)
            if player not in cells:
                score -= {1: 1, 2: 10}.get(cells.count(3 - player), 0)
        return score

    def move_id(self, move: Move) -> str:
        return f"{columns(3)[move % 3]}{move // 3 + 1}"

    def render(self, viewer: int) -> str:
        rows = ["  a b c"]
        for r in range(3):
            rows.append(f"{r + 1} " + " ".join(SYMBOLS[self.board[r * 3 + c]] for c in range(3)))
        return "\n".join(rows)
