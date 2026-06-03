from sqlmodel import Session, SQLModel, create_engine

from app.models import JoinBlacklist
from app.services.join_blacklist import get_enabled_blacklist_item


def test_get_enabled_blacklist_item_returns_enabled_match() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(JoinBlacklist(user_id=1001, enabled=True, reason="blocked"))
        session.commit()

        item = get_enabled_blacklist_item(session, 1001)

    assert item is not None
    assert item.reason == "blocked"


def test_get_enabled_blacklist_item_ignores_disabled_match() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(JoinBlacklist(user_id=1001, enabled=False))
        session.commit()

        item = get_enabled_blacklist_item(session, 1001)

    assert item is None
