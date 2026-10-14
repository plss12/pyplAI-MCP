import random

import pytest

from pyplai_mcp.games import GAMES, Phantom, TicTacToe, UltimateTicTacToe
from pyplai_mcp.games.ultimate import DRAWN


def play(game, *moves):
    for text in moves:
        game.apply(game.parse_move(text))
    return game


@pytest.mark.parametrize("name", list(GAMES))
def test_move_ids_round_trip(name):
    game = GAMES[name]()
    for move in game.legal_moves():
        assert game.parse_move(game.move_id(move)) == move
        assert game.parse_move(game.move_id(move).upper()) == move


@pytest.mark.parametrize("name", list(GAMES))
def test_random_games_finish(name):
    rng = random.Random(0)
    for _ in range(50):
        game = GAMES[name]()
        turns = 0
        while game.winner() is None:
            game.apply(rng.choice(game.legal_moves()))
            turns += 1
            assert turns < 500
        assert game.legal_moves() == [] or game.winner() in (1, 2)


def test_tictactoe_win_and_coordinates():
    game = play(TicTacToe(), "a1", "a2", "b1", "b2", "c1")
    assert game.winner() == 1
    assert game.render(1).splitlines()[1] == "1 X X X"


def test_parse_move_rejects_illegal_moves():
    game = play(TicTacToe(), "b2")
    with pytest.raises(ValueError):
        game.parse_move("b2")
    with pytest.raises(ValueError):
        game.parse_move("d9")


def test_ultimate_sends_opponent_to_matching_board():
    game = play(UltimateTicTacToe(), "B2:c1")
    assert {game.move_id(m).split(":")[0] for m in game.legal_moves()} == {"C1"}


def test_ultimate_full_board_without_winner_frees_the_next_player():
    game = UltimateTicTacToe()
    # Fill A1 with no three in a row, always sending the next move back to A1
    for cell in ["a1", "b1", "c1", "b2", "a2", "c2", "b3", "a3", "c3"]:
        game.target = 0
        game.apply(game.parse_move("A1:" + cell))
    assert game.main[0] == DRAWN
    game.target = 0
    boards = {game.move_id(m).split(":")[0] for m in game.legal_moves()}
    assert len(boards) == 8 and "A1" not in boards
    assert game.winner() is None


def test_phantom_bump_discovers_the_stone_and_keeps_the_turn():
    game = play(Phantom(), "a1")  # player 1 places on a1
    play(game, "a1")  # player 2 bumps into it
    assert game.jugadorActual == 2 and 0 in game.discovered[2] and game.bumped
    assert "a1" not in [game.move_id(m) for m in game.legal_moves()]
    assert game.render(2).splitlines()[1].startswith("1 o")


def test_phantom_render_hides_opponent_stones():
    game = play(Phantom(), "a1", "d4", "b1")
    assert game.render(2).count("Y") == 1 and "o" not in game.render(2)
    assert game.render(1).count("Y") == 2


def test_phantom_determinization_keeps_what_the_player_knows():
    random.seed(3)
    game = play(Phantom(), "a1", "d4", "b1", "a1", "c4")  # player 2 discovers a1, then places c4
    # Player 1 to move: knows a1 and b1 are theirs and that player 2 has 2 hidden stones
    for _ in range(200):
        sample = game.determinize()
        assert sample.board[0] == sample.board[1] == 1
        assert sum(1 for v in sample.board if v == 2) == 2
        assert sample.discovered[2] == set()
    seen = {tuple(i for i, v in enumerate(game.determinize().board) if v == 2) for _ in range(200)}
    assert len(seen) > 10
