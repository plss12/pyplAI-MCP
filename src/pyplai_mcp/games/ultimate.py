"""Ultimate tic-tac-toe: nine tic-tac-toe boards arranged in a 3x3 grid."""

from __future__ import annotations

from typing import Self

from .base import Game, Move, find_lines

LINES = find_lines(3, 3)
SYMBOLS = {0: ".", 1: "X", 2: "O"}
# Value of a closed small board on the main board when it filled up with no winner
DRAWN = 3


class UltimateTicTacToe(Game):
    name = "ultimate"
    title = "Ultimate tic-tac-toe"
    summary = "Nine tic-tac-toe boards inside a big one; each move sends the opponent to a board. Perfect information."
    perfect_information = True
    move_format = "Board and cell, such as B2:a1 (centre board, top-left cell). Boards use A-C and 1-3, cells a-c and 1-3."
    rules = """# Ultimate tic-tac-toe

The board is a 3x3 grid of small tic-tac-toe boards. Player 1 plays X and moves first.

- Win a small board by getting three in a row inside it. That board is then closed and counts as
  yours on the big board. A small board that fills up with no winner is closed as a draw.
- The cell you play inside a small board decides where your opponent plays next: playing the
  top-right cell sends them to the top-right board.
- If you are sent to a closed board, you may play in any open board.
- Win the game by getting three small boards in a row on the big board. If no moves are left, the
  game is a draw.

Moves are written as `Board:cell`. Boards are named with an uppercase column and a row (`A1` is the
top-left board, `C3` the bottom-right) and cells with a lowercase column and a row (`a1` to `c3`).
For example, `B2:a1` is the top-left cell of the centre board.
"""

    def __init__(self) -> None:
        super().__init__()
        # cells[b][c]: cell c (0-8) of small board b (0-8), both in reading order
        self.cells = [[0] * 9 for _ in range(9)]
        # main[b]: 0 open, 1 or 2 won by that player, DRAWN closed with no winner
        self.main = [0] * 9
        # Board the player to move is sent to, or None to play anywhere
        self.target: int | None = None

    def legal_moves(self) -> list[Move]:
        if self.is_winner(1) or self.is_winner(2):
            return []
        boards = [self.target] if self.target is not None and self.main[self.target] == 0 else range(9)
        return [b * 9 + c for b in boards if self.main[b] == 0 for c in range(9) if self.cells[b][c] == 0]

    def apply(self, move: Move) -> Self:
        board, cell = divmod(move, 9)
        player = self.jugadorActual
        self.cells[board][cell] = player
        if any(all(self.cells[board][i] == player for i in line) for line in LINES):
            self.main[board] = player
        elif all(self.cells[board]):
            self.main[board] = DRAWN
        self.target = cell
        self.jugadorActual = 3 - player
        return self

    def is_winner(self, player: int) -> bool:
        return any(all(self.main[i] == player for i in line) for line in LINES)

    def heuristic(self, player: int) -> float:
        rival = 3 - player

        def open_twos(values: list[int], who: int) -> int:
            return sum(1 for line in LINES if [values[i] for i in line].count(who) == 2 and [values[i] for i in line].count(0) == 1)

        score = 0.0
        # Small boards won, with extra weight for the centre and the corners
        for b, value in enumerate(self.main):
            weight = 5 + (10 if b == 4 else 3 if b in (0, 2, 6, 8) else 0)
            score += weight if value == player else -weight if value == rival else 0
        score += 4 * (open_twos(self.main, player) - open_twos(self.main, rival))
        for b in range(9):
            if self.main[b] == 0:
                score += 2 * (open_twos(self.cells[b], player) - open_twos(self.cells[b], rival))
                centre = self.cells[b][4]
                score += 3 if centre == player else -3 if centre == rival else 0
        return score

    def move_id(self, move: Move) -> str:
        board, cell = divmod(move, 9)
        return f"{'ABC'[board % 3]}{board // 3 + 1}:{'abc'[cell % 3]}{cell // 3 + 1}"

    def render(self, viewer: int) -> str:
        lines = ["    A       B       C"]
        for big_row in range(3):
            if big_row:
                lines.append("  ------+-------+------")
            for small_row in range(3):
                parts = []
                for big_col in range(3):
                    board = big_row * 3 + big_col
                    parts.append(" ".join(SYMBOLS[self.cells[board][small_row * 3 + c]] for c in range(3)))
                label = f"{big_row + 1} " if small_row == 1 else "  "
                lines.append(label + " | ".join(parts))
        return "\n".join(lines)

    def notes(self, viewer: int) -> list[str]:
        names = {1: "X", 2: "O", DRAWN: "drawn"}
        closed = [f"{'ABC'[b % 3]}{b // 3 + 1} {names[v]}" for b, v in enumerate(self.main) if v]
        notes = ["Closed boards: " + (", ".join(closed) if closed else "none") + "."]
        if self.winner() is None:
            if self.target is not None and self.main[self.target] == 0:
                notes.append(f"The player to move must play in board {'ABC'[self.target % 3]}{self.target // 3 + 1}.")
            else:
                notes.append("The player to move may play in any open board.")
        return notes
