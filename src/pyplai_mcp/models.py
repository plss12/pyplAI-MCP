"""Structured results returned by the tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GameInfo(BaseModel):
    name: str = Field(description="Identifier to pass to new_game.")
    title: str
    summary: str
    perfect_information: bool = Field(description="False when some information is hidden from each player.")
    move_format: str
    opponents: list[str] = Field(description="Opponents available in new_game.")
    analysis_algorithms: list[str] = Field(description="Algorithms available in analyze_position.")


class GameState(BaseModel):
    game_id: str
    game: str
    you_are: int = Field(description="Your player number. Player 1 moves first.")
    status: Literal["your_turn", "you_won", "you_lost", "draw"]
    board: str = Field(description="The board as you see it.")
    notes: list[str] = Field(description="Facts about the position you are allowed to know.")
    legal_moves: list[str] = Field(description="Moves you can play now. Empty when the game is over.")
    history: list[str] = Field(description="Everything that has happened, as you saw it.")
    opponent: str


class MoveResult(BaseModel):
    your_move: str
    outcome: str = Field(description="What happened after your move, including your opponent's reply.")
    state: GameState


class MoveEvaluation(BaseModel):
    move: str
    visits: int = Field(description="Times the search explored this move (0 for minimax).")
    value: float = Field(description="Win rate from 0 to 1 for Monte Carlo searches (a draw counts 0.5), or the minimax score.")


class Analysis(BaseModel):
    game_id: str
    algorithm: str
    metric: Literal["win_rate", "minimax_score"]
    best_move: str
    moves: list[MoveEvaluation] = Field(description="Best moves first.")
    iterations: int = Field(description="Search iterations, or positions evaluated for minimax.")
    seconds: float
    note: str


class GameOver(BaseModel):
    game_id: str
    removed: bool
