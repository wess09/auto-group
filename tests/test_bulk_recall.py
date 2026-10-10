import asyncio
import sqlite3
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, create_engine, select

from app.bot import events
from app.core.config import Settings
from app.models import AuditLog, RecallAdmin
from app.services import bulk_recall, message_cache
from app.services.admin import jobs, runtime
from app.services.message_cache import MESSAGE_CACHE_CAPACITY, MessageCache


@pytest.fixture
def cache(tmp_path, monkeypatch):
    cache = MessageCache(tmp_path / "messages.db")
    monkeypatch.setattr(message_cache, "get_message_cache", lambda: cache)
    settings = Settings(
        _env_file=None, message_recall_concurrency=4, message_recall_timeout_seconds=0.2
    )
    monkeypatch.setattr(bulk_recall, "get_settings", lambda: settings)
    monkeypatch.setattr(bulk_recall, "recall_limit", lambda: semaphore)
    semaphore = asyncio.Semaphore(settings.message_recall_concurrency)
    bulk_recall.active_groups.clear()
    yield cache
    cache.close()
    bulk_recall.active_groups.clear()


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'management.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(runtime, "engine", engine)
    with Session(engine) as session:
        session.add(RecallAdmin(user_id=42))
        session.add(RecallAdmin(user_id=43, enabled=False))
        session.commit()
    yield engine
    engine.dispose()


class FakeBot:
    self_id = "123"

    def __init__(self, failures=(), stalled=None):
        self.calls = []
        self.completed = []
        self.replies = []
        self.failures = failures
        self.stalled = stalled
        self.running = self.peak = 0
        self.release = asyncio.Event()
        self.started = asyncio.Event()

    async def call_api(self, api, **data):
        if api == "send_group_msg":
            self.replies.append(data["message"][0]["data"]["text"])
            return {"message_id": 99999}
        assert api == "delete_msg"
        assert data["_timeout"] == 0.2
        message_id = data["message_id"]
        self.calls.append(message_id)
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            if message_id == self.stalled:
                self.started.set()
                await self.release.wait()
            else:
                await asyncio.sleep(0)
            if message_id in self.failures:
                raise RuntimeError("无法撤回")
            self.completed.append(message_id)
        finally:
            self.running -= 1


def record(cache, message_id, *, bot_id="123", group_id=1001, command=False):
    return cache.record(bot_id, group_id, message_id, 42, 100, command)[0]


def event(text="普通消息", *, message_id=100, user_id=42, group_id=1001):
    return SimpleNamespace(
        user_id=user_id,
        group_id=group_id,
        message_id=message_id,
        time=100,
        get_plaintext=lambda: text,
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("/大记忆清除术", 500),
        (" /大记忆清除术  \n", 500),
        ("/大记忆清除术 1", 1),
        ("/大记忆清除术 20000", 20000),
    ],
)
def test_command_count(text, expected):
    assert bulk_recall.is_recall_command(text)
    assert bulk_recall.parse_count(text) == expected


@pytest.mark.parametrize("argument", ["0", "-1", "20001", "1.5", "abc", "10 20", "9" * 1000])
def test_invalid_count(argument):
    with pytest.raises(ValueError):
        bulk_recall.parse_count("/大记忆清除术 " + argument)


def test_command_must_start_at_text_boundary():
    for text in ("普通文字 /大记忆清除术", "大记忆清除术", "/大记忆清除术后缀"):
        assert not bulk_recall.is_recall_command(text)


def test_cache_is_bounded_persistent_and_duplicate_events_do_not_reorder(tmp_path):
    path = tmp_path / "cache.db"
    cache = MessageCache(path)
    try:
        for message_id in range(MESSAGE_CACHE_CAPACITY + 10):
            record(cache, message_id)
        assert cache.count == MESSAGE_CACHE_CAPACITY
        sequence, created = cache.record("123", 1001, 10, 42, 100)
        assert not created
        assert sequence < record(cache, 20010)
        assert cache.count == MESSAGE_CACHE_CAPACITY
    finally:
        cache.close()
    reopened = MessageCache(path)
    try:
        rows = reopened.latest("123", 1001, 20000, 999999)
        assert reopened.count == len(rows) == MESSAGE_CACHE_CAPACITY
        assert rows[0][1] == 20010
        assert rows[-1][1] == 11
        assert "recall_admins" not in {
            row[0] for row in reopened.connection.execute("SELECT name FROM sqlite_master")
        }
    finally:
        reopened.close()


def test_cache_snapshot_isolates_group_bot_commands_and_recalled_messages(cache):
    record(cache, 1)
    recalled = record(cache, 2)
    record(cache, 3, group_id=2002)
    record(cache, 1, bot_id="other")
    record(cache, 4, command=True)
    cache.mark_recalled([recalled])
    before = record(cache, 5, command=True)
    record(cache, 6)
    assert [row[1] for row in cache.latest("123", 1001, 500, before)] == [1]
    cache.record_recall("other", 1001, 1)
    assert cache.latest("other", 1001, 500, before) == []
    assert [row[1] for row in cache.latest("123", 1001, 500, before)] == [1]


def test_cache_write_failure_rolls_back_without_premature_eviction(tmp_path, monkeypatch):
    cache = MessageCache(tmp_path / "cache.db", capacity=2)
    try:
        record(cache, 1)

        def fail():
            raise sqlite3.OperationalError("write failure")

        with monkeypatch.context() as patch:
            patch.setattr(cache, "_prune", fail)
            with pytest.raises(sqlite3.OperationalError):
                record(cache, 2)
        record(cache, 3)
        assert cache.count == 2
        assert [row[1] for row in cache.latest("123", 1001, 500, 9999)] == [3, 1]
    finally:
        cache.close()


@pytest.mark.asyncio
async def test_cancellation_stops_workers_and_remembers_completed_recalls(cache):
    for message_id in range(1, 9):
        record(cache, message_id)
    before = record(cache, 99, command=True)
    bot = FakeBot(stalled=8)
    task = asyncio.create_task(bulk_recall.recall_recent(bot, 1001, 500, before))
    await bot.started.wait()
    while len(bot.completed) < 7:
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert bot.running == 0
    assert [row[1] for row in cache.latest("123", 1001, 500, before)] == [8]


@pytest.mark.asyncio
async def test_failure_and_timeout_skip_without_blocking_other_workers(cache):
    for message_id in range(1, 13):
        record(cache, message_id)
    before = record(cache, 99, command=True)
    bot = FakeBot(failures={9, 10}, stalled=12)
    task = asyncio.create_task(bulk_recall.recall_recent(bot, 1001, 500, before))
    await bot.started.wait()

    # All remaining work can finish while the first request is still pending.
    async def others_done():
        while len(bot.completed) < 9:
            await asyncio.sleep(0)

    await asyncio.wait_for(others_done(), timeout=0.15)
    assert not task.done() and not bot.release.is_set()
    result = await task
    assert result.selected == 12 and result.succeeded == 9 and result.failed == 3
    assert bot.peak == 4 and set(bot.calls) == set(range(1, 13))
    assert bot.running == 0
    assert {row[1] for row in cache.latest("123", 1001, 500, before)} == {9, 10, 12}


@pytest.mark.asyncio
async def test_all_unrecallable_messages_are_attempted(cache):
    for message_id in range(1, 41):
        record(cache, message_id)
    before = record(cache, 99, command=True)
    bot = FakeBot(failures=set(range(1, 41)))
    result = await bulk_recall.recall_recent(bot, 1001, 40, before)
    assert result.succeeded == 0 and result.failed == 40
    assert len(bot.calls) == 40 and bot.peak == 4


@pytest.mark.asyncio
async def test_concurrency_limit_is_shared_across_groups(cache):
    for message_id in range(1, 21):
        record(cache, message_id, group_id=1001 if message_id <= 10 else 2002)
    before = record(cache, 99, command=True)
    bot = FakeBot()
    await asyncio.gather(
        bulk_recall.recall_recent(bot, 1001, 500, before),
        bulk_recall.recall_recent(bot, 2002, 500, before),
    )
    assert len(bot.calls) == 20 and bot.peak <= 4


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id", [43, 999])
async def test_disabled_and_unknown_admins_cannot_recall(cache, db, user_id):
    record(cache, 1)
    bot = FakeBot()
    assert await bulk_recall.handle_message(bot, event("/大记忆清除术", user_id=user_id))
    assert bot.calls == [] and "没有批量撤回权限" in bot.replies[0]
    assert not bulk_recall.active_groups


@pytest.mark.asyncio
async def test_command_runs_in_background_and_reports_audit_and_duplicate(cache, db, monkeypatch):
    for message_id in range(1, 11):
        record(cache, message_id)
    bot = FakeBot(failures={10})
    release = asyncio.Event()
    run_command = bulk_recall.run_command

    async def held_command(*args):
        await release.wait()
        await run_command(*args)

    monkeypatch.setattr(bulk_recall, "run_command", held_command)
    message = event("/大记忆清除术 3")
    assert await bulk_recall.handle_message(bot, message)
    assert bulk_recall.active_groups == {("123", 1001)}
    running = list(jobs.tasks)
    assert await bulk_recall.handle_message(bot, message)
    assert list(jobs.tasks) == running
    assert await bulk_recall.handle_message(bot, event("/大记忆清除术", message_id=101))
    assert any("正在执行" in text for text in bot.replies)
    release.set()
    await asyncio.gather(*running)
    assert not bulk_recall.active_groups
    assert set(bot.calls) == {8, 9, 10}
    assert any("成功 2 条，失败并跳过 1 条" in text for text in bot.replies)
    with Session(db) as session:
        audit = session.exec(
            select(AuditLog).where(AuditLog.action == "messages.bulk-recall")
        ).one()
        assert audit.detail["operator_qq"] == 42 and audit.detail["failed"] == 1


@pytest.mark.asyncio
async def test_default_count_and_empty_cache(cache, db, monkeypatch):
    for message_id in range(1, 602):
        record(cache, message_id)
    bot = FakeBot()
    await bulk_recall.handle_message(bot, event("/大记忆清除术", message_id=1000))
    await asyncio.gather(*list(jobs.tasks))
    assert len(bot.calls) == 500 and set(bot.calls) == set(range(102, 602))
    await bulk_recall.handle_message(bot, event("/大记忆清除术", message_id=1001, group_id=3003))
    await asyncio.gather(*list(jobs.tasks))
    assert "只有 0 条" in bot.replies[-1]


@pytest.mark.asyncio
async def test_invalid_command_does_not_start_task(cache, db):
    bot = FakeBot()
    await bulk_recall.handle_message(bot, event("/大记忆清除术 20001"))
    assert bot.calls == [] and "用法" in bot.replies[0]


@pytest.mark.asyncio
async def test_regular_messages_are_cached_without_admin_database_query(cache, monkeypatch):
    async def unexpected(*args):
        pytest.fail("ordinary messages must not query command permissions")

    monkeypatch.setattr(bulk_recall, "database", unexpected)
    assert not await bulk_recall.handle_message(FakeBot(), event())
    assert [row[1] for row in cache.latest("123", 1001, 500, 9999)] == [100]


@pytest.mark.asyncio
async def test_event_handler_stops_propagation_only_for_commands(cache, db):
    matcher = SimpleNamespace(block=False)
    matcher.stop_propagation = lambda: setattr(matcher, "block", True)
    await events.cache_group_message(FakeBot(), event(), matcher)
    assert not matcher.block
    await events.cache_group_message(FakeBot(), event("/大记忆清除术 0", message_id=101), matcher)
    assert matcher.block


@pytest.mark.asyncio
async def test_group_recall_notice_updates_the_cache(cache):
    record(cache, 1)
    await events.handle_group_member_change(
        SimpleNamespace(
            notice_type="group_recall",
            self_id=123,
            group_id=1001,
            message_id=1,
        )
    )
    assert cache.latest("123", 1001, 500, 9999) == []


def test_recall_settings_have_bounds():
    for params in (
        {"message_recall_concurrency": 0},
        {"message_recall_concurrency": 129},
        {"message_recall_timeout_seconds": 0},
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **params)


def test_message_cache_cannot_share_the_management_database(tmp_path, monkeypatch):
    path = tmp_path / "management.db"
    settings = Settings(
        _env_file=None, database_url=f"sqlite:///{path}", message_cache_path=str(path)
    )
    monkeypatch.setattr(message_cache, "get_settings", lambda: settings)
    message_cache.get_message_cache.cache_clear()
    try:
        with pytest.raises(ValueError, match="独立数据库"):
            message_cache.get_message_cache()
        assert not path.exists()
    finally:
        message_cache.get_message_cache.cache_clear()
