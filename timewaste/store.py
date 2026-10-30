"""SQLite storage for conversations and time-wasted stats."""

import sqlite3
import time
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id      INTEGER PRIMARY KEY,
    title        TEXT NOT NULL DEFAULT '',
    persona      TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    started_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id  INTEGER NOT NULL REFERENCES chats(chat_id),
    role     TEXT NOT NULL CHECK (role IN ('scammer', 'bait')),
    text     TEXT NOT NULL,
    ts       REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_chat ON messages(chat_id, id);
"""


@dataclass
class Chat:
    chat_id: int
    title: str
    persona: str
    active: bool
    started_at: float


@dataclass
class Stats:
    chats: int
    scammer_messages: int
    bait_messages: int
    # Sum over chats of (last scammer message - first scammer message).
    seconds_wasted: float


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def get_chat(self, chat_id: int) -> Chat | None:
        row = self.db.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
        if row is None:
            return None
        return Chat(row["chat_id"], row["title"], row["persona"], bool(row["active"]), row["started_at"])

    def activate(self, chat_id: int, persona: str, title: str = "") -> None:
        self.db.execute(
            """INSERT INTO chats (chat_id, title, persona, active, started_at)
               VALUES (?, ?, ?, 1, ?)
               ON CONFLICT(chat_id) DO UPDATE SET active = 1, persona = excluded.persona,
                   title = CASE WHEN excluded.title != '' THEN excluded.title ELSE chats.title END""",
            (chat_id, title, persona, time.time()),
        )
        self.db.commit()

    def deactivate(self, chat_id: int) -> None:
        self.db.execute("UPDATE chats SET active = 0 WHERE chat_id = ?", (chat_id,))
        self.db.commit()

    def reset(self, chat_id: int) -> None:
        self.db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        self.db.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
        self.db.commit()

    def add_message(self, chat_id: int, role: str, text: str) -> None:
        self.db.execute(
            "INSERT INTO messages (chat_id, role, text, ts) VALUES (?, ?, ?, ?)",
            (chat_id, role, text, time.time()),
        )
        self.db.commit()

    def history(self, chat_id: int, limit: int = 60) -> list[tuple[str, str]]:
        rows = self.db.execute(
            "SELECT role, text FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
        return [(r["role"], r["text"]) for r in reversed(rows)]

    def stats(self) -> Stats:
        counts = self.db.execute(
            """SELECT COUNT(DISTINCT chat_id) AS chats,
                      SUM(role = 'scammer') AS scammer,
                      SUM(role = 'bait') AS bait
               FROM messages"""
        ).fetchone()
        wasted = self.db.execute(
            """SELECT COALESCE(SUM(span), 0) FROM (
                   SELECT MAX(ts) - MIN(ts) AS span FROM messages
                   WHERE role = 'scammer' GROUP BY chat_id)"""
        ).fetchone()[0]
        return Stats(counts["chats"] or 0, counts["scammer"] or 0, counts["bait"] or 0, wasted)


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = [f"{v}{u}" for v, u in ((days, "d"), (hours, "h"), (minutes, "m")) if v]
    return " ".join(parts) or f"{seconds}s"


def format_stats(stats: Stats) -> str:
    return (
        f"Scammers engaged: {stats.chats}\n"
        f"Messages they wrote: {stats.scammer_messages}\n"
        f"Replies we sent: {stats.bait_messages}\n"
        f"Time wasted: {format_duration(stats.seconds_wasted)}"
    )
