"""In-memory store of the games in progress."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field

from .engines import Engine
from .games import Game


@dataclass
class Session:
    id: str
    game: Game
    human: int
    opponent_name: str
    opponent: Engine
    # What the human has seen happen, in order
    events: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_used: float = field(default_factory=time.monotonic)


class SessionStore:
    """Thread-safe registry with a size cap and an idle timeout."""

    def __init__(self, max_sessions: int = 100, ttl_seconds: float = 3600) -> None:
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def add(self, game: Game, human: int, opponent_name: str, opponent: Engine) -> Session:
        with self._lock:
            self._expire()
            if len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions.values(), key=lambda s: s.last_used)
                del self._sessions[oldest.id]
            session = Session(secrets.token_hex(4), game, human, opponent_name, opponent)
            self._sessions[session.id] = session
            return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            self._expire()
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_used = time.monotonic()
            return session

    def remove(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def __len__(self) -> int:
        return len(self._sessions)

    def _expire(self) -> None:
        now = time.monotonic()
        for session_id in [s.id for s in self._sessions.values() if now - s.last_used > self.ttl_seconds]:
            del self._sessions[session_id]
