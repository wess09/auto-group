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
    if not inspector.has_table("message_moderation_rules"):
        return
    columns = {
        column["name"] for column in inspector.get_columns("message_moderation_rules")
    }
    with engine.begin() as connection:
        if "cloud_review_enabled" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE message_moderation_rules "
                    "ADD COLUMN cloud_review_enabled BOOLEAN NOT NULL DEFAULT 0"
                )
            )


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _upgrade_sqlite_schema()
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
