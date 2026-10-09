from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from app.core import database
from app.models import JoinRequest, ManagedGroup, MessageModerationRule


def test_startup_upgrades_legacy_sqlite_and_preserves_rows(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)
    with Session(engine) as session:
        session.add_all(
            [
                ManagedGroup(group_id=1001, name="原群配置"),
                MessageModerationRule(name="原审核规则"),
                JoinRequest(flag="old", group_id=1001, user_id=42, result="approved"),
            ]
        )
        session.commit()
    with engine.begin() as connection:
        for table, fields in (
            ("managed_groups", ["min_qq_level", "max_wrong_answers", "wrong_answer_window_hours"]),
            (
                "message_moderation_rules",
                ["cloud_review_enabled", "ocr_enabled", "image_review_enabled"],
            ),
            ("join_requests", ["qq_level", "wrong_answer_count", "apply_status", "apply_error"]),
        ):
            for field in fields:
                connection.execute(text(f"ALTER TABLE {table} DROP COLUMN {field}"))
    database.init_db()
    database.init_db()
    with Session(engine) as session:
        group = session.exec(select(ManagedGroup)).one()
        rule = session.exec(select(MessageModerationRule)).one()
        request = session.exec(select(JoinRequest)).one()
        assert group.name == "原群配置" and group.min_qq_level == group.max_wrong_answers == 0
        assert group.wrong_answer_window_hours == 24
        assert rule.name == "原审核规则" and not rule.image_review_enabled and not rule.ocr_enabled
        assert request.result == "approved" and request.apply_status == "legacy"
        assert request.qq_level is None and request.wrong_answer_count == 0
    engine.dispose()
