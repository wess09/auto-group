import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import AnswerRule, AuditLog, JoinBlacklist, JoinRequest, ManagedGroup
from app.services.admin import bot_data, runtime
from app.services.join_requests import extract_qq_level, process_join_request


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'joins.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(runtime, "engine", engine)
    with Session(engine) as session:
        session.add(
            ManagedGroup(group_id=1001, name="测试群", min_qq_level=16, max_wrong_answers=3)
        )
        session.add(AnswerRule(name="答案", patterns=["正确答案"], match_mode="exact"))
        session.commit()
    yield engine
    engine.dispose()


def attempt(session, flag, answer="错误", group_id=1001, user_id=42, level=20):
    return bot_data.decide_and_record_join(
        session,
        {
            "flag": flag,
            "group_id": group_id,
            "user_id": user_id,
            "answer_text": answer,
            "raw_event": {},
        },
        level,
    )[0]


@pytest.mark.parametrize(
    "info,expected",
    [
        ({"qq_level": 16}, 16),
        ({"qqLevel": "32"}, 32),
        ({"level": "20"}, 20),
        ({"qq_level": 0, "level": 100}, 0),
        ({"level": "活跃"}, None),
        ({"qqLevel": True}, None),
        ({"qqLevel": -1}, None),
        ({"qqLevel": 1.5}, None),
        ({"vip_level": 8}, None),
        (None, None),
    ],
)
def test_qq_level_fields(info, expected):
    assert extract_qq_level(info) == expected


def test_level_gate_does_not_count_as_wrong_answer(db):
    with Session(db) as session:
        assert attempt(session, "low", answer="正确答案", level=15)["result"] == "level_rejected"
        assert attempt(session, "unknown", level=None)["result"] == "level_unknown"
        decision = attempt(session, "ok", answer="正确答案", level=16)
        assert decision["result"] == "approved"
        assert decision["wrong_answer_count"] == 0
        assert not session.exec(select(JoinBlacklist)).all()


def test_threshold_replays_notes_and_global_blacklist(db):
    with Session(db) as session:
        assert attempt(session, "one")["wrong_answer_count"] == 1
        assert attempt(session, "one")["wrong_answer_count"] == 1
        assert attempt(session, "two")["wrong_answer_count"] == 2
        decision = attempt(session, "three", answer="最后错误答案")
        assert decision["result"] == "blacklisted"
        assert decision["wrong_answer_count"] == 3
        item = session.exec(select(JoinBlacklist)).one()
        for content in (
            "测试群",
            "1001",
            "42",
            "24 小时",
            "错误次数：3",
            "阈值：3",
            "最后错误答案",
            "UTC+8",
        ):
            assert content in item.note
        assert "3 次" in item.reason
        assert len(session.exec(select(JoinRequest)).all()) == 3
        assert (
            len(session.exec(select(AuditLog).where(AuditLog.action == "blacklist.auto")).all())
            == 1
        )
        assert (
            attempt(session, "other", group_id=2002, answer="正确答案")["result"] == "blacklisted"
        )


def test_replayed_approval_cannot_bypass_new_blacklist(db):
    with Session(db) as session:
        assert attempt(session, "old-approval", answer="正确答案")["result"] == "approved"
        session.add(JoinBlacklist(user_id=42, reason="管理员拉黑"))
        session.commit()
        decision = attempt(session, "old-approval", answer="正确答案")
        assert decision["result"] == "blacklisted" and decision["reason"] == "管理员拉黑"
        assert decision["matched_rule_id"] is None
        assert len(session.exec(select(JoinRequest)).all()) == 1


def test_window_success_and_disabled_blacklist_reset_counts(db):
    with Session(db) as session:
        old = JoinRequest(
            flag="old",
            group_id=1001,
            user_id=42,
            result="rejected",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        session.add(old)
        session.commit()
        assert attempt(session, "one")["wrong_answer_count"] == 1
        assert attempt(session, "ok", answer="正确答案")["result"] == "approved"
        assert attempt(session, "two")["wrong_answer_count"] == 1
        attempt(session, "three")
        attempt(session, "four")
        item = session.exec(select(JoinBlacklist)).one()
        item.enabled = False
        item.note = "人工解除；保留原备注"
        item.updated_at = datetime.now(timezone.utc)
        session.add(item)
        session.commit()
        assert attempt(session, "five")["wrong_answer_count"] == 1
        attempt(session, "six")
        assert attempt(session, "seven")["result"] == "blacklisted"
        assert session.exec(select(JoinBlacklist)).one().note.startswith("人工解除；保留原备注\n")


def test_redirects_and_other_users_do_not_count(db):
    with Session(db) as session:
        session.add(ManagedGroup(group_id=2002, priority=1, max_wrong_answers=3))
        session.commit()
        assert attempt(session, "redirect", group_id=2002)["result"] == "redirected"
        assert attempt(session, "other", user_id=99)["wrong_answer_count"] == 1
        assert attempt(session, "one")["wrong_answer_count"] == 1
        group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == 1001)).one()
        group.max_wrong_answers = 0
        group.min_qq_level = 0
        session.add(group)
        session.commit()
        assert attempt(session, "off", level=None)["result"] == "rejected"
        assert not session.exec(select(JoinBlacklist)).all()


class FakeBot:
    def __init__(self, *, level=20, fail=False):
        self.level, self.fail = level, fail
        self.calls = []

    async def call_api(self, api, **data):
        self.calls.append((api, data))
        if api == "get_stranger_info":
            return {"qqLevel": self.level}
        if self.fail:
            raise RuntimeError("OneBot offline")


@pytest.mark.asyncio
async def test_failed_onebot_retry_and_concurrent_replays_only_count_once(db):
    data = {
        "flag": "retry",
        "group_id": 1001,
        "user_id": 42,
        "answer_text": "错误",
        "raw_event": {},
    }
    bot = FakeBot(fail=True)
    with pytest.raises(RuntimeError, match="offline"):
        await process_join_request(bot, data)
    with Session(db) as session:
        row = session.exec(select(JoinRequest)).one()
        assert row.apply_status == "failed"
        assert row.wrong_answer_count == 1
    bot.fail = False
    await asyncio.gather(process_join_request(bot, data), process_join_request(bot, data))
    with Session(db) as session:
        row = session.exec(select(JoinRequest)).one()
        assert row.apply_status == "success" and not row.apply_error
        assert row.wrong_answer_count == 1
    assert bot.calls[0][0] == "get_stranger_info"
    assert bot.calls[0][1]["no_cache"] is True
    assert all(
        call[1].get("approve") is False for call in bot.calls if call[0] == "set_group_add_request"
    )


@pytest.mark.asyncio
async def test_unmanaged_and_disabled_groups_are_ignored(db):
    bot = FakeBot()
    data = {"flag": "ignored", "group_id": 2002, "user_id": 42, "answer_text": "", "raw_event": {}}
    assert await process_join_request(bot, data) is None
    with Session(db) as session:
        group = session.exec(select(ManagedGroup)).one()
        group.enabled = False
        session.add(group)
        session.commit()
    data["group_id"] = 1001
    assert await process_join_request(bot, data) is None
    assert not bot.calls
