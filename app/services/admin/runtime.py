import asyncio
import threading
from collections.abc import Callable
from typing import Any, TypeVar

import anyio
from sqlalchemy import event
from sqlalchemy.orm import Session as SASession
from sqlmodel import Session

from app.core.database import engine


T = TypeVar("T")
limiter = anyio.CapacityLimiter(4)


async def database(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    def work() -> T:
        with Session(engine) as session:
            return fn(session, *args, **kwargs)

    return await anyio.to_thread.run_sync(work, limiter=limiter)


class ChangeHub:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.listeners: dict[asyncio.Queue, set[str]] = {}
        self.pending: dict[str, dict] = {}
        self.timer: asyncio.TimerHandle | None = None
        self.versions: dict[str, int] = {}
        self.lock = threading.Lock()

    def start(self) -> None:
        if self.loop is not asyncio.get_running_loop() and self.timer:
            self.timer.cancel()
            self.timer = None
            self.pending.clear()
        self.loop = asyncio.get_running_loop()

    def committed(self, topics: dict[str, dict]) -> None:
        with self.lock:
            for topic in topics:
                self.versions[topic] = self.versions.get(topic, 0) + 1
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.enqueue, topics)

    def enqueue(self, topics: dict[str, dict]) -> None:
        # Scope changes are represented by topics; payloads never contain rows.
        self.pending.update(topics)
        if self.timer is None:
            self.timer = self.loop.call_later(1, self.flush) if self.loop else None

    def flush(self) -> None:
        pending, self.pending = self.pending, {}
        self.timer = None
        for queue, subscriptions in list(self.listeners.items()):
            for topic, payload in pending.items():
                if topic not in subscriptions:
                    continue
                try:
                    queue.put_nowait({"v": 1, "type": "event", "topic": topic, "payload": payload})
                except asyncio.QueueFull:
                    # Disconnect slow readers so they recover through a fresh query.
                    subscriptions.clear()
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait({"close": 1013})
                    break


hub = ChangeHub()
MODEL_TOPICS = {
    "managed_groups": "groups",
    "answer_rules": "rules",
    "join_blacklist": "blacklist",
    "message_moderation_rules": "moderation",
    "dedupe_whitelist": "whitelist",
    "recall_admins": "recall-admins",
    "announcements": "notices",
    "essence_messages": "essence",
    "group_files": "files",
    "join_requests": "joins",
    "leave_events": "leaves",
    "audit_logs": "audits",
    "member_activity_stats": "activity",
    "admin_jobs": "jobs",
    "admin_job_items": "job-items",
    "dedupe_actions": "actions",
    "dedupe_jobs": "dedupe",
    "tencentcloud_tms_config": "cloud",
    "image_review_config": "image-review",
}
TOPICS = set(MODEL_TOPICS.values()) | {
    "dashboard.summary",
    "dashboard.trends",
    "dashboard.breakdown",
    "dashboard.rankings",
    "dashboard.recent",
}


def valid_topic(topic: str) -> bool:
    if topic in TOPICS:
        return True
    prefix, _, identifier = topic.partition(":")
    return prefix in TOPICS and identifier.isdigit()


@event.listens_for(SASession, "before_flush")
def remember_changes(session: SASession, *_: Any) -> None:
    topics = session.info.setdefault("admin_changes", {})
    for row in session.new | session.dirty | session.deleted:
        topic = MODEL_TOPICS.get(getattr(row, "__tablename__", ""))
        if not topic:
            continue
        topics[topic] = {}
        group_id = getattr(row, "group_id", None)
        if group_id:
            topics[f"{topic}:{group_id}"] = {"group_id": group_id}
        if topic == "jobs" and row.id:
            topics[f"jobs:{row.id}"] = {"id": row.id}
        if topic == "job-items":
            topics[f"jobs:{row.job_id}"] = {"id": row.job_id}
        if topic in {
            "groups",
            "joins",
            "leaves",
            "audits",
            "activity",
            "notices",
            "files",
            "essence",
        }:
            topics["dashboard.summary"] = {}
        if topic in {"joins", "leaves", "audits", "activity"}:
            topics["dashboard.trends"] = {}
        if topic == "joins":
            topics["dashboard.breakdown"] = {}
        if topic in {"groups", "activity"}:
            topics["dashboard.rankings"] = {}
        if topic in {"leaves", "audits"}:
            topics["dashboard.recent"] = {}


@event.listens_for(SASession, "after_commit")
def publish_committed(session: SASession) -> None:
    hub.committed(session.info.pop("admin_changes", {}))


@event.listens_for(SASession, "after_rollback")
def discard_changes(session: SASession) -> None:
    session.info.pop("admin_changes", None)
