"""Games available on the server."""

from .base import Game
from .phantom import Phantom
from .tictactoe import TicTacToe
from .ultimate import UltimateTicTacToe

GAMES: dict[str, type[Game]] = {game.name: game for game in (TicTacToe, UltimateTicTacToe, Phantom)}

__all__ = ["GAMES", "Game", "Phantom", "TicTacToe", "UltimateTicTacToe"]
