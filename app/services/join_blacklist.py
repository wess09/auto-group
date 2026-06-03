from sqlmodel import Session, select

from app.models import JoinBlacklist


def get_enabled_blacklist_item(session: Session, user_id: int) -> JoinBlacklist | None:
    return session.exec(
        select(JoinBlacklist).where(
            JoinBlacklist.user_id == user_id,
            JoinBlacklist.enabled == True,  # noqa: E712
        )
    ).first()
