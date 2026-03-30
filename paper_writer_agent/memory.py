from __future__ import annotations

import sqlite3
import threading
from collections import deque
from dataclasses import dataclass


@dataclass
class MemoryItem:
    role: str
    content: str


class WorkingMemory:
    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.buffer: deque[MemoryItem] = deque(maxlen=capacity)

    def add(self, role: str, content: str) -> None:
        self.buffer.append(MemoryItem(role=role, content=content))

    def snapshot(self) -> list[MemoryItem]:
        return list(self.buffer)


class LongTermMemory:
    def __init__(self, db_path: str = "memory.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag TEXT NOT NULL,
                    content TEXT NOT NULL
                )
                """
            )
            self.conn.commit()

    def add(self, tag: str, content: str) -> None:
        with self._lock:
            self.conn.execute("INSERT INTO memories(tag, content) VALUES (?, ?)", (tag, content))
            self.conn.commit()

    def search(self, tag: str, limit: int = 5) -> list[str]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT content FROM memories WHERE tag = ? ORDER BY id DESC LIMIT ?",
                (tag, limit),
            ).fetchall()
        return [r[0] for r in rows]

    def close(self) -> None:
        with self._lock:
            self.conn.close()


class MemoryManager:
    def __init__(self, working: WorkingMemory, long_term: LongTermMemory):
        self.working = working
        self.long_term = long_term

    def remember_turn(self, role: str, content: str, tag: str = "dialogue") -> None:
        self.working.add(role, content)
        self.long_term.add(tag, f"{role}: {content}")

    def build_memory_summary(self) -> str:
        short = "\n".join([f"- {m.role}: {m.content}" for m in self.working.snapshot()])
        long_recent = self.long_term.search("review", limit=3)
        long_text = "\n".join([f"- {x}" for x in long_recent])
        return f"[Working Memory]\n{short}\n\n[Long-term Review Memory]\n{long_text}".strip()

    def close(self) -> None:
        self.long_term.close()
