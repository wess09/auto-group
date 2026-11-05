"""Close connected admin WebSockets after a committed account revocation."""

import asyncio
import threading


_lock = threading.Lock()
_connections: dict[int, dict[asyncio.Queue, asyncio.AbstractEventLoop]] = {}


def register(admin_id: int, queue: asyncio.Queue) -> None:
    with _lock:
        _connections.setdefault(admin_id, {})[queue] = asyncio.get_running_loop()


def unregister(admin_id: int, queue: asyncio.Queue) -> None:
    with _lock:
        entries = _connections.get(admin_id, {})
        entries.pop(queue, None)
        if not entries:
            _connections.pop(admin_id, None)


def revoke(admin_id: int) -> None:
    with _lock:
        entries = list(_connections.get(admin_id, {}).items())
    for queue, loop in entries:
        if loop.is_closed():
            continue

        def close(queue=queue):
            while not queue.empty():
                queue.get_nowait()
            queue.put_nowait({"close": 4001})

        try:
            loop.call_soon_threadsafe(close)
        except RuntimeError:
            pass  # A loop that closed concurrently has no live session left to revoke.
