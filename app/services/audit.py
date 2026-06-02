from typing import Any

from sqlmodel import Session

from app.models import Admin, AuditLog


def add_audit(
    session: Session,
    action: str,
    target: str = "",
    detail: dict[str, Any] | None = None,
    admin: Admin | None = None,
) -> None:
    session.add(
        AuditLog(
            admin_id=admin.id if admin else None,
            action=action,
            target=target,
            detail=detail or {},
        )
    )
    session.commit()
