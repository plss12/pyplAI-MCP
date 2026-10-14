"""MCP server that lets a language model play board games with pyplAI's search algorithms as tools."""

from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import engines
from .games import GAMES, Game, Phantom
from .models import Analysis, GameInfo, GameOver, GameState, MoveEvaluation, MoveResult
from .sessions import Session, SessionStore

GameName = Literal["tictactoe", "ultimate", "phantom"]
OpponentName = Literal["auto", "random", "mcts", "minimax", "so-ismcts", "mo-ismcts"]
AlgorithmName = Literal["auto", "mcts", "minimax", "so-ismcts", "mo-ismcts"]

INSTRUCTIONS = """\
Play board games against search algorithms from the pyplAI library, and use those same
algorithms to analyse your own positions.

1. list_games shows the games. Read rules://<game> for the full rules.
2. new_game starts a game against an opponent. Whenever you get a state back it is your turn,
   unless the game is over: the opponent replies inside play_move.
3. analyze_position runs a search (Monte Carlo tree search, minimax or information set MCTS)
   from your position and ranks your legal moves.
4. play_move plays one of the legal moves exactly as written.

In Phantom you cannot see your opponent's stones. The board and the analysis only use what you
know: information set searches sample where the hidden stones could be.
"""

mcp = MCPServer("pyplai", instructions=INSTRUCTIONS)
store = SessionStore()

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def _game_class(name: str) -> type[Game]:
    try:
        return GAMES[name]
    except KeyError:
        raise ToolError(f"Unknown game {name!r}. Available games: {', '.join(GAMES)}.") from None


def _session(game_id: str) -> Session:
    session = store.get(game_id)
    if session is None:
        raise ToolError(f"No game with id {game_id!r}. It may have finished long ago; start one with new_game.")
    return session


def _player_label(game: Game, player: int) -> str:
    if isinstance(game, Phantom):
        return f"player {player}"
    return f"player {player} ({'X' if player == 1 else 'O'})"


def _state(session: Session) -> GameState:
    game = session.game
    winner = game.winner()
    status: Literal["your_turn", "you_won", "you_lost", "draw"]
    if winner is None:
        status = "your_turn"
    elif winner == 0:
        status = "draw"
    else:
        status = "you_won" if winner == session.human else "you_lost"
    notes = [f"You are {_player_label(game, session.human)}.", *game.notes(session.human)]
    if isinstance(game, Phantom) and winner is not None:
        notes.append("The game is over, so here is the full board (1 = player 1, 2 = player 2):\n" + game.render_full())
    return GameState(
        game_id=session.id,
        game=game.name,
        you_are=session.human,
        status=status,
        board=game.render(session.human),
        notes=notes,
        legal_moves=[game.move_id(m) for m in game.legal_moves()] if winner is None else [],
        history=list(session.events),
        opponent=session.opponent_name,
    )


def _describe_own_move(game: Game, move_text: str, before_player: int) -> str:
    if isinstance(game, Phantom) and game.jugadorActual == before_player and game.winner() is None:
        return f"You tried {move_text}: it holds a hidden opponent stone. You discovered it and must move again."
    return f"You played {move_text}."


def _opponent_turns(session: Session) -> list[str]:
    """Let the opponent move until it is the human's turn again or the game ends."""
    game = session.game
    events = []
    while game.winner() is None and game.jugadorActual != session.human:
        result = engines.search(session.opponent, game)
        move = result.best
        text = game.move_id(move)
        game.apply(move)
        if isinstance(game, Phantom):
            # The human only learns that the turn came back: never where the opponent played
            if game.jugadorActual == session.human:
                events.append("Your opponent placed a stone somewhere you cannot see.")
        else:
            events.append(f"Your opponent ({session.opponent_name}) played {text}.")
    return events


def _result_line(session: Session) -> list[str]:
    winner = session.game.winner()
    if winner is None:
        return []
    if winner == 0:
        return ["The game ended in a draw."]
    return ["You won the game." if winner == session.human else "You lost the game."]


@mcp.tool(annotations=READ_ONLY)
def list_games() -> list[GameInfo]:
    """List the games you can play, their move format and the algorithms available for each."""
    return [
        GameInfo(
            name=game.name,
            title=game.title,
            summary=game.summary,
            perfect_information=game.perfect_information,
            move_format=game.move_format,
            opponents=["auto", *engines.engines_for(game)],
            analysis_algorithms=["auto", *[e for e in engines.engines_for(game) if e != "random"]],
        )
        for game in GAMES.values()
    ]


@mcp.tool()
def new_game(
    game: Annotated[GameName, Field(description="Game to play. See list_games.")],
    play_as: Annotated[Literal[1, 2], Field(description="Your player number. Player 1 moves first.")] = 1,
    opponent: Annotated[OpponentName, Field(description="Opponent algorithm. auto picks the strongest fair one for the game.")] = "auto",
    opponent_seconds: Annotated[float, Field(ge=0.05, le=10, description="Thinking time per move for Monte Carlo opponents.")] = 1.0,
    minimax_depth: Annotated[int, Field(ge=1, le=9, description="Search depth (moves ahead) for the minimax opponent.")] = 4,
    opening: Annotated[
        list[str] | None,
        Field(description="Moves to play from the start, for both players, before the game is handed over. Use it to set up a position."),
    ] = None,
    seed: Annotated[int | None, Field(description="Seed for the opponent's search, to make its play reproducible.")] = None,
) -> GameState:
    """Start a game against a pyplAI algorithm. If the opponent moves first, it has already moved in the returned state."""
    cls = _game_class(game)
    name = engines.default_analysis_engine(cls) if opponent == "auto" else opponent
    try:
        engine = engines.build(cls, name, seconds=opponent_seconds, depth=minimax_depth, seed=seed)
    except ValueError as error:
        raise ToolError(str(error)) from None
    state = cls()
    events = []
    for number, text in enumerate(opening or [], start=1):
        if state.winner() is not None:
            raise ToolError(f"The game is already over before opening move {number} ({text!r}).")
        try:
            move = state.parse_move(text)
        except ValueError:
            legal = ", ".join(state.move_id(m) for m in state.legal_moves())
            raise ToolError(f"Opening move {number} ({text!r}) is not legal there. Legal moves: {legal}.") from None
        player = state.jugadorActual
        state.apply(move)
        verb = "tried" if isinstance(state, Phantom) and state.jugadorActual == player and state.winner() is None else "played"
        events.append(f"Opening: {_player_label(state, player)} {verb} {text}.")
    session = store.add(state, play_as, name, engine)
    with session.lock:
        session.events.extend(events)
        session.events.extend(_opponent_turns(session))
        session.events.extend(_result_line(session))
        return _state(session)


@mcp.tool(annotations=READ_ONLY)
def get_state(game_id: Annotated[str, Field(description="Id returned by new_game.")]) -> GameState:
    """Show the board as you see it, your legal moves and what has happened so far."""
    session = _session(game_id)
    with session.lock:
        return _state(session)


@mcp.tool()
def play_move(
    game_id: Annotated[str, Field(description="Id returned by new_game.")],
    move: Annotated[str, Field(description="One of the legal moves, as written in legal_moves.")],
) -> MoveResult:
    """Play a move. The opponent replies straight away, so the returned state is your next turn (or the end of the game)."""
    session = _session(game_id)
    with session.lock:
        game = session.game
        if game.winner() is not None:
            raise ToolError("This game is over. Start another one with new_game.")
        try:
            parsed = game.parse_move(move)
        except ValueError:
            legal = ", ".join(game.move_id(m) for m in game.legal_moves())
            raise ToolError(f"{move!r} is not a legal move. Legal moves: {legal}.") from None
        text = game.move_id(parsed)
        player = game.jugadorActual
        game.apply(parsed)
        events = [_describe_own_move(game, text, player)]
        events.extend(_opponent_turns(session))
        events.extend(_result_line(session))
        session.events.extend(events)
        return MoveResult(your_move=text, outcome=" ".join(events), state=_state(session))


@mcp.tool(annotations=READ_ONLY)
def analyze_position(
    game_id: Annotated[str, Field(description="Id returned by new_game.")],
    algorithm: Annotated[
        AlgorithmName, Field(description="Search to run. auto uses MCTS for perfect-information games and MO-ISMCTS for Phantom.")
    ] = "auto",
    seconds: Annotated[float, Field(ge=0.1, le=10, description="Search time for Monte Carlo algorithms.")] = 2.0,
    minimax_depth: Annotated[int, Field(ge=1, le=9, description="Depth (moves ahead) for minimax.")] = 4,
    top_k: Annotated[int, Field(ge=1, le=81, description="How many of the best moves to return.")] = 5,
) -> Analysis:
    """Rank your legal moves with a search from the current position. It only uses information you have."""
    session = _session(game_id)
    with session.lock:
        game = session.game
        if game.winner() is not None:
            raise ToolError("This game is over, so there is nothing to analyse.")
        snapshot = deepcopy(game)
    cls = type(snapshot)
    name = engines.default_analysis_engine(cls) if algorithm == "auto" else algorithm
    try:
        engine = engines.build(cls, name, seconds=seconds, depth=minimax_depth)
    except ValueError as error:
        raise ToolError(str(error)) from None
    result = engines.search(engine, snapshot)
    if name == "minimax":
        note = (
            f"Alpha-beta minimax {minimax_depth} moves ahead. Scores near +1e9 are forced wins and near -1e9 forced losses; "
            "other scores come from a heuristic."
        )
    elif name == "mcts":
        note = "Monte Carlo tree search (UCT). value is the share of simulated games won after each move, counting draws as half."
    else:
        note = (
            f"{name.upper()} (information set MCTS). Each iteration samples where the hidden opponent stones could be "
            "from what you know, so the search never sees the real hidden stones. value is the share of simulated games won."
        )
    return Analysis(
        game_id=session.id,
        algorithm=name,
        metric="minimax_score" if name == "minimax" else "win_rate",
        best_move=snapshot.move_id(result.best),
        moves=[MoveEvaluation(move=snapshot.move_id(e.move), visits=e.visits, value=round(e.value, 4)) for e in result.moves[:top_k]],
        iterations=result.iterations,
        seconds=round(result.seconds, 3),
        note=note,
    )


@mcp.tool()
def end_game(game_id: Annotated[str, Field(description="Id returned by new_game.")]) -> GameOver:
    """Forget a game you no longer need."""
    return GameOver(game_id=game_id, removed=store.remove(game_id))


@mcp.resource("rules://{game}", mime_type="text/markdown")
def rules(game: str) -> str:
    """Full rules and move notation of a game."""
    return _game_class(game).rules


@mcp.prompt()
def play_game(game: str = "ultimate", opponent: str = "auto") -> str:
    """Play a full game, using the search tools to choose and explain each move."""
    return (
        f"Let's play {game} against the {opponent} opponent of the pyplai server. Read rules://{game} first, "
        f"then start with new_game. Before each of your moves, call analyze_position, pick a move and explain "
        f"in one or two sentences why, quoting the numbers from the analysis. Then call play_move and tell me "
        f"what the opponent did. Keep going until the game ends."
    )
