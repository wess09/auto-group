from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, col, create_engine, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Admin


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


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
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
