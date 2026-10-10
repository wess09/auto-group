"""A bounded, metadata-only SQLite cache, separate from the management database."""

import sqlite3
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import anyio

from app.core.config import get_settings


MESSAGE_CACHE_CAPACITY = 20_000
cache_limiter = anyio.CapacityLimiter(1)


class MessageCache:
    def __init__(self, path: Path, capacity: int = MESSAGE_CACHE_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError("缓存容量必须大于 0")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.capacity = capacity
        self.lock = threading.Lock()
        self.connection = sqlite3.connect(path, timeout=5, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id TEXT NOT NULL,
                group_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                sent_at INTEGER NOT NULL,
                is_command INTEGER NOT NULL DEFAULT 0,
                recalled INTEGER NOT NULL DEFAULT 0,
                UNIQUE (bot_id, message_id)
            );
            CREATE INDEX IF NOT EXISTS ix_messages_recall
                ON messages (bot_id, group_id, recalled, is_command, id DESC);
            """
        )
        self.count = self.connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        with self.connection:
            self._prune()

    def _prune(self) -> None:
        excess = self.count - self.capacity
        if excess > 0:
            self.connection.execute(
                "DELETE FROM messages WHERE id IN (SELECT id FROM messages ORDER BY id LIMIT ?)",
                (excess,),
            )
            self.count = self.capacity

    def record(
        self,
        bot_id: str,
        group_id: int,
        message_id: int,
        user_id: int,
        sent_at: int,
        is_command: bool = False,
    ) -> tuple[int, bool]:
        with self.lock:
            previous_count = self.count
            try:
                with self.connection:
                    cursor = self.connection.execute(
                        "INSERT INTO messages "
                        "(bot_id, group_id, message_id, user_id, sent_at, is_command) "
                        "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (bot_id, message_id) DO NOTHING",
                        (bot_id, group_id, message_id, user_id, sent_at, is_command),
                    )
                    created = cursor.rowcount == 1
                    if created:
                        self.count += 1
                        self._prune()
                        return int(cursor.lastrowid), True
                    row = self.connection.execute(
                        "SELECT id FROM messages WHERE bot_id = ? AND message_id = ?",
                        (bot_id, message_id),
                    ).fetchone()
                    return row[0], False
            except Exception:
                # A rolled-back insert must not affect the next eviction decision.
                self.count = previous_count
                raise

    def latest(
        self, bot_id: str, group_id: int, count: int, before_id: int
    ) -> list[tuple[int, int]]:
        with self.lock:
            return self.connection.execute(
                "SELECT id, message_id FROM messages "
                "WHERE bot_id = ? AND group_id = ? AND recalled = 0 AND is_command = 0 "
                "AND id < ? ORDER BY id DESC LIMIT ?",
                (bot_id, group_id, before_id, count),
            ).fetchall()

    def mark_recalled(self, ids: list[int]) -> None:
        if not ids:
            return
        with self.lock, self.connection:
            self.connection.executemany(
                "UPDATE messages SET recalled = 1 WHERE id = ?",
                ((identifier,) for identifier in ids),
            )

    def record_recall(self, bot_id: str, group_id: int, message_id: int) -> None:
        with self.lock, self.connection:
            self.connection.execute(
                "UPDATE messages SET recalled = 1 "
                "WHERE bot_id = ? AND group_id = ? AND message_id = ?",
                (bot_id, group_id, message_id),
            )

    def close(self) -> None:
        with self.lock:
            self.connection.close()


@lru_cache
def get_message_cache() -> MessageCache:
    settings = get_settings()
    path = Path(settings.message_cache_path).resolve()
    if settings.database_url.startswith("sqlite:///"):
        management_path = Path(settings.database_url.removeprefix("sqlite:///")).resolve()
        if path == management_path:
            raise ValueError("消息缓存必须使用独立数据库，请修改 MESSAGE_CACHE_PATH")
    return MessageCache(path)


async def cache_io(method: str, *args: Any) -> Any:
    def work() -> Any:
        cache = get_message_cache()
        return getattr(cache, method)(*args)

    return await anyio.to_thread.run_sync(work, limiter=cache_limiter)


async def init_message_cache() -> None:
    await anyio.to_thread.run_sync(get_message_cache, limiter=cache_limiter)


def close_message_cache() -> None:
    if get_message_cache.cache_info().currsize:
        get_message_cache().close()
        get_message_cache.cache_clear()
