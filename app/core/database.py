from pathlib import Path
from typing import Iterator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, col, create_engine, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Admin, TencentCloudTmsConfig


settings = get_settings()
if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.replace("sqlite:///", "", 1)
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


def _upgrade_sqlite_schema() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    additions = {
        "message_moderation_rules": {
            "cloud_review_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            "ocr_enabled": "BOOLEAN NOT NULL DEFAULT 0",
            "image_review_enabled": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "managed_groups": {
            "min_qq_level": "INTEGER NOT NULL DEFAULT 0",
            "max_wrong_answers": "INTEGER NOT NULL DEFAULT 0",
            "wrong_answer_window_hours": "INTEGER NOT NULL DEFAULT 24",
        },
        "join_requests": {
            "qq_level": "INTEGER",
            "wrong_answer_count": "INTEGER NOT NULL DEFAULT 0",
            "apply_status": "VARCHAR NOT NULL DEFAULT 'legacy'",
            "apply_error": "VARCHAR NOT NULL DEFAULT ''",
        },
    }
    with engine.begin() as connection:
        for table, additions_for_table in additions.items():
            if not inspector.has_table(table):
                continue
            columns = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in additions_for_table.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _upgrade_sqlite_schema()
    with engine.begin() as connection:
        for table, columns in (
            ("join_requests", "created_at, id"),
            ("leave_events", "created_at, id"),
            ("audit_logs", "created_at, id"),
            ("announcements", "group_id, synced_at, id"),
            ("essence_messages", "group_id, synced_at, id"),
            ("dedupe_actions", "job_id, id"),
            ("admin_job_items", "job_id, id"),
            ("member_activity_stats", "stat_date, group_id, user_id"),
        ):
            connection.execute(
                text(f"CREATE INDEX IF NOT EXISTS ix_{table}_admin_page ON {table} ({columns})")
            )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_join_requests_failures "
                "ON join_requests (group_id, user_id, created_at, result)"
            )
        )
    with Session(engine) as session:
        config = session.exec(select(TencentCloudTmsConfig)).first()
        if not config:
            session.add(TencentCloudTmsConfig())
        admin = session.exec(
            select(Admin).where(col(Admin.username) == settings.admin_username)
        ).first()
        if not admin:
            session.add(
                Admin(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                )
            )
        session.commit()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
