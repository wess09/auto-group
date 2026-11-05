import asyncio
import base64
import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import Settings
from app.models import AuditLog, ManagedGroup
from app.models.entities import JoinVerification
from app.services import join_verification as verification
from app.services.admin import runtime


class FakeBot:
    def __init__(self, bot_id="123", failures=()):
        self.self_id = bot_id
        self.calls = []
        self.failures = set(failures)

    async def call_api(self, api, **data):
        self.calls.append((api, data))
        await asyncio.sleep(0)
        if api in self.failures:
            raise RuntimeError("sensitive remote response must not be recorded")
        return {"message_id": 999}

    def actions(self, api):
        return [data for name, data in self.calls if name == api]

    def texts(self):
        return [
            segment["data"]["text"]
            for data in self.actions("send_group_msg")
            for segment in data["message"]
            if segment["type"] == "text"
        ]


@pytest.fixture
def clock(monkeypatch):
    clock = SimpleNamespace(now=datetime(2026, 11, 5, tzinfo=timezone.utc))
    clock.advance = lambda seconds: setattr(clock, "now", clock.now + timedelta(seconds=seconds))
    monkeypatch.setattr(verification, "now_utc", lambda: clock.now)
    return clock


@pytest.fixture
def db(tmp_path, monkeypatch, clock):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'verification.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(runtime, "engine", engine)
    monkeypatch.setattr(verification, "generate_captcha", lambda: ("A2BCD", b"test-png"))
    monkeypatch.setattr(
        verification,
        "get_settings",
        lambda: Settings(_env_file=None, onebot_api_timeout_seconds=0.2),
    )
    with Session(engine) as session:
        session.add_all(
            [
                ManagedGroup(group_id=1001, join_verification_enabled=True),
                ManagedGroup(group_id=1002, join_verification_enabled=False),
                ManagedGroup(group_id=1003, enabled=False, join_verification_enabled=True),
                ManagedGroup(group_id=1004, join_verification_enabled=True),
            ]
        )
        session.commit()
    yield engine
    engine.dispose()


def notice(clock, kind="group_increase", *, group_id=1001, user_id=42, time=None):
    return SimpleNamespace(
        notice_type=kind,
        group_id=group_id,
        user_id=user_id,
        time=int(clock.now.timestamp()) if time is None else time,
    )


def message(clock, text="wrong", *, message_id=1, group_id=1001, user_id=42, time=None):
    return SimpleNamespace(
        group_id=group_id,
        user_id=user_id,
        message_id=message_id,
        time=int(clock.now.timestamp()) if time is None else time,
        get_plaintext=lambda: text,
    )


def state(db, *, group_id=1001, user_id=42, bot_id="123"):
    with Session(db) as session:
        return session.exec(
            select(JoinVerification).where(
                JoinVerification.bot_id == bot_id,
                JoinVerification.group_id == group_id,
                JoinVerification.user_id == user_id,
            )
        ).one()


def test_library_generates_random_png_without_plaintext_metadata():
    first, png = verification.generate_captcha()
    second, _ = verification.generate_captcha()
    assert len(first) == verification.CAPTCHA_LENGTH
    assert set(first) <= set(verification.CAPTCHA_ALPHABET)
    assert first != second
    with Image.open(io.BytesIO(png)) as image:
        assert image.format == "PNG" and image.size == (240, 90)
        assert not image.info
        image.verify()


@pytest.mark.parametrize("group_id,user_id", [(1002, 42), (1003, 42), (9999, 42), (1001, 123)])
async def test_disabled_unmanaged_groups_and_bot_itself_are_ignored(db, clock, group_id, user_id):
    bot = FakeBot()
    await verification.handle_notice(bot, notice(clock, group_id=group_id, user_id=user_id))
    assert not bot.calls
    assert not await verification.handle_message(
        bot, message(clock, group_id=group_id, user_id=user_id)
    )
    with Session(db) as session:
        assert not session.exec(select(JoinVerification)).all()


async def test_welcome_mentions_only_newcomer_and_sends_inline_image(db, clock):
    bot = FakeBot()
    joined = notice(clock)
    await asyncio.gather(*(verification.handle_notice(bot, joined) for _ in range(5)))
    assert len(bot.calls) == 1
    data = bot.actions("send_group_msg")[0]
    assert data["group_id"] == 1001 and data["_timeout"] == 0.2
    assert data["message"][0] == {"type": "at", "data": {"qq": "42"}}
    encoded = data["message"][2]["data"]["file"].removeprefix("base64://")
    assert base64.b64decode(encoded) == b"test-png"
    assert "欢迎" in bot.texts()[0] and "A2BCD" not in bot.texts()[0]
    row = state(db)
    assert row.status == "pending" and row.delivered and row.wrong_attempts == 0
    assert "A2BCD" not in row.model_dump_json()


async def test_correct_answer_is_normalized_and_does_not_verify_again(db, clock):
    bot = FakeBot()
    joined = notice(clock)
    await verification.handle_notice(bot, joined)
    assert await verification.handle_message(bot, message(clock, " ａ２ｂｃｄ \n"))
    assert state(db).status == "verified" and not state(db).answer_hash
    assert "验证通过" in bot.texts()[-1]
    assert not await verification.handle_message(bot, message(clock, "hello", message_id=2))
    await verification.handle_notice(bot, joined)
    assert len(bot.actions("send_group_msg")) == 2
    assert not bot.actions("set_group_ban") and not bot.actions("set_group_kick")


async def test_four_wrong_answers_mute_for_10_20_30_then_kick(db, clock):
    bot = FakeBot()
    await verification.handle_notice(bot, notice(clock))
    for index, seconds in enumerate((10, 20, 30), start=1):
        assert await verification.handle_message(bot, message(clock, message_id=index))
        assert state(db).wrong_attempts == index
        assert bot.actions("set_group_ban")[-1]["duration"] == seconds
        assert f"已禁言 {seconds} 秒" in bot.texts()[-1]
        clock.advance(seconds + 1)
    await verification.handle_message(bot, message(clock, message_id=4))
    assert [data["duration"] for data in bot.actions("set_group_ban")] == [10, 20, 30]
    assert bot.actions("set_group_kick") == [
        {"group_id": 1001, "user_id": 42, "reject_add_request": False, "_timeout": 0.2}
    ]
    assert state(db).status == "kicked" and state(db).wrong_attempts == 4
    assert "已移出" in bot.texts()[-1]
    assert not await verification.handle_message(bot, message(clock, message_id=5))


async def test_cooldown_duplicate_and_delayed_reports_do_not_count(db, clock):
    bot = FakeBot()
    await verification.handle_notice(bot, notice(clock))
    wrong = message(clock)
    await asyncio.gather(*(verification.handle_message(bot, wrong) for _ in range(6)))
    assert state(db).wrong_attempts == 1 and len(bot.actions("set_group_ban")) == 1
    cooldown_message = message(clock, "A2BCD", message_id=2)
    await verification.handle_message(bot, cooldown_message)
    await verification.handle_message(bot, message(clock, "/验证码", message_id=3))
    assert state(db).status == "pending" and len(bot.actions("send_group_msg")) == 2
    clock.advance(11)
    await verification.handle_message(bot, wrong)
    await verification.handle_message(bot, cooldown_message)
    await verification.handle_message(bot, message(clock, message_id=4, time=wrong.time))
    assert state(db).wrong_attempts == 1
    await verification.handle_message(bot, message(clock, "a2bcd", message_id=5))
    assert state(db).status == "verified"


async def test_refresh_and_expiry_preserve_wrong_count(db, clock):
    bot = FakeBot()
    await verification.handle_notice(bot, notice(clock))
    await verification.handle_message(bot, message(clock))
    clock.advance(11)
    await verification.handle_message(bot, message(clock, "/验证码", message_id=2))
    assert state(db).wrong_attempts == 1
    clock.advance(verification.CAPTCHA_LIFETIME_SECONDS + 1)
    await verification.handle_message(bot, message(clock, "A2BCD", message_id=3))
    assert state(db).status == "pending" and state(db).wrong_attempts == 1
    assert "已刷新" in bot.texts()[-1]
    await verification.handle_message(bot, message(clock, "A2BCD", message_id=4))
    assert state(db).status == "verified"


async def test_failed_delivery_retries_without_charging_an_attempt(db, clock):
    bot = FakeBot(failures={"send_group_msg"})
    await verification.handle_notice(bot, notice(clock))
    assert not state(db).delivered
    bot.failures.clear()
    await verification.handle_message(bot, message(clock))
    assert state(db).delivered and state(db).wrong_attempts == 0
    assert "已刷新" in bot.texts()[-1]


async def test_failed_mute_still_enforces_cooldown_and_does_not_claim_success(db, clock):
    bot = FakeBot(failures={"set_group_ban"})
    await verification.handle_notice(bot, notice(clock))
    await verification.handle_message(bot, message(clock))
    assert "处理失败" in bot.texts()[-1] and "已禁言" not in bot.texts()[-1]
    await verification.handle_message(bot, message(clock, message_id=2))
    assert state(db).wrong_attempts == 1
    clock.advance(11)
    await verification.handle_message(bot, message(clock, "A2BCD", message_id=3))
    assert state(db).status == "verified"


async def test_failed_kick_cannot_be_bypassed_by_correct_answer_and_is_audited(db, clock):
    bot = FakeBot(failures={"set_group_kick"})
    await verification.handle_notice(bot, notice(clock))
    for index in range(1, 5):
        await verification.handle_message(bot, message(clock, message_id=index))
        clock.advance(31)
    assert state(db).status == "kick_pending"
    assert "处理失败" in bot.texts()[-1] and "已移出" not in bot.texts()[-1]
    bot.failures.clear()
    await verification.handle_message(bot, message(clock, "A2BCD", message_id=5))
    assert state(db).status == "kicked" and state(db).wrong_attempts == 4
    with Session(db) as session:
        audits = session.exec(select(AuditLog).where(AuditLog.action == "verification.kick")).all()
        assert [row.detail["success"] for row in audits] == [False, True]
        assert audits[0].detail["error"] == "RuntimeError"
        assert all("sensitive" not in row.model_dump_json() for row in audits)


async def test_groups_users_and_connected_bots_have_separate_challenges(db, clock):
    bot, other = FakeBot(), FakeBot("456")
    await verification.handle_notice(bot, notice(clock))
    await verification.handle_notice(bot, notice(clock, user_id=43))
    await verification.handle_notice(bot, notice(clock, group_id=1004))
    await verification.handle_notice(other, notice(clock))
    await verification.handle_message(bot, message(clock))
    assert state(db).wrong_attempts == 1
    assert state(db, user_id=43).wrong_attempts == 0
    assert state(db, group_id=1004).wrong_attempts == 0
    assert state(db, bot_id="456").wrong_attempts == 0
    assert not await verification.handle_message(bot, message(clock, user_id=999))


async def test_leave_rejoin_and_stale_notices(db, clock):
    bot = FakeBot()
    joined = notice(clock)
    await verification.handle_notice(bot, joined)
    await verification.handle_message(bot, message(clock))
    clock.advance(1)
    left = notice(clock, "group_decrease")
    await verification.handle_notice(bot, left)
    assert state(db).status == "left" and not state(db).answer_hash
    clock.advance(1)
    await verification.handle_notice(bot, notice(clock))
    assert state(db).status == "pending" and state(db).wrong_attempts == 0
    await verification.handle_notice(bot, joined)
    await verification.handle_notice(bot, left)
    assert state(db).status == "pending"
    await verification.handle_message(bot, message(clock, time=joined.time))
    assert state(db).wrong_attempts == 0


async def test_bot_removal_clears_pending_group_challenges(db, clock):
    bot = FakeBot()
    for user_id in (42, 43):
        await verification.handle_notice(bot, notice(clock, user_id=user_id))
    await verification.handle_notice(bot, notice(clock, "group_decrease", user_id=123))
    assert state(db).status == state(db, user_id=43).status == "left"


async def test_disabling_verification_cancels_pending_and_reenable_ignores_old_members(db, clock):
    bot = FakeBot()
    await verification.handle_notice(bot, notice(clock))
    with Session(db) as session:
        group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == 1001)).one()
        group.join_verification_enabled = False
        session.add(group)
        session.commit()
    assert not await verification.handle_message(bot, message(clock))
    assert state(db).status == "cancelled"
    with Session(db) as session:
        group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == 1001)).one()
        group.join_verification_enabled = True
        session.add(group)
        session.commit()
    assert not await verification.handle_message(bot, message(clock, message_id=2))


async def test_state_survives_reopening_database_and_empty_media_does_not_fail(db, clock):
    bot = FakeBot()
    await verification.handle_notice(bot, notice(clock))
    await verification.handle_message(bot, message(clock, ""))
    assert state(db).wrong_attempts == 0
    await verification.handle_message(bot, message(clock, message_id=2))
    db.dispose()
    clock.advance(11)
    await verification.handle_message(FakeBot(), message(clock, message_id=3))
    assert state(db).wrong_attempts == 2


async def test_api_timeout_is_bounded_and_sanitized(monkeypatch):
    class StalledBot(FakeBot):
        async def call_api(self, api, **data):
            await asyncio.Event().wait()

    monkeypatch.setattr(
        verification, "get_settings", lambda: SimpleNamespace(onebot_api_timeout_seconds=0.01)
    )
    assert await verification._api(StalledBot(), "send_group_msg", group_id=1001) == "TimeoutError"


@pytest.mark.parametrize("has_image", [False, True])
async def test_event_handler_intercepts_answers_and_keeps_image_moderation(
    db, clock, monkeypatch, has_image
):
    from app.bot import events

    bot = FakeBot()
    await events.handle_join_verification_notice(bot, notice(clock))
    executions = []

    async def cache_message(bot, event, *, execute_commands=True):
        executions.append(execute_commands)
        return False

    monkeypatch.setattr(events.bulk_recall, "handle_message", cache_message)
    matcher = SimpleNamespace(block=False)
    matcher.stop_propagation = lambda: setattr(matcher, "block", True)
    event = message(clock, "/大记忆清除术")
    event.message = (
        [{"type": "image", "data": {"url": "https://example.com/image.png"}}] if has_image else []
    )
    await events.cache_group_message(bot, event, matcher)
    assert matcher.block is not has_image and executions == [False]
    assert state(db).wrong_attempts == 1
