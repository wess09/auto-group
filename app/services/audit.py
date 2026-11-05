from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel
from sqlalchemy import event
from sqlalchemy.orm import Session as SASession

from sqlmodel import Session

from app.models import Admin, AuditLog
from app.core.config import get_settings
from app.services.auth_rate_limit import get_client_ip


context: ContextVar[dict[str, Any]] = ContextVar("audit_context", default={})
SECRET_FIELDS = {
    "password",
    "password_hash",
    "current_password",
    "new_password",
    "secret_key",
    "secret_id",
    "api_key",
    "totp_secret",
    "totp_code",
    "code",
    "token",
    "access_token",
    "authorization",
    "secret",
    "otpauth_uri",
    "proxy_url",
    "captchaVerifyParam",
}
SECRET_FIELDS_NORMALIZED = {key.lower() for key in SECRET_FIELDS}


def redact(value: Any) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {
            str(key): "[已隐藏]"
            if str(key).lower().replace("-", "_") in SECRET_FIELDS_NORMALIZED
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def request_context(admin: Admin | Any, connection: Any, request_id: str = "") -> dict:
    settings = get_settings()
    return {
        "admin_id": admin.id if admin else None,
        "actor_username": admin.username if admin else "",
        "actor_name": admin.display_name if admin else "",
        "client_ip": get_client_ip(connection, settings.login_rate_limit_trust_proxy_headers)[:100],
        "user_agent": connection.headers.get("user-agent", "")[:512],
        "request_id": request_id or getattr(connection.state, "audit_request_id", ""),
        "transport": "ws" if connection.scope.get("type") == "websocket" else "http",
    }


@contextmanager
def scope(data: dict):
    token = context.set(data)
    try:
        yield
    finally:
        context.reset(token)


@event.listens_for(SASession, "before_flush")
def enrich_audits(session: SASession, *_: Any) -> None:
    for row in list(session.new):
        if not isinstance(row, AuditLog):
            continue
        data = context.get()
        if row.admin_id is not None and data.get("admin_id") not in {None, row.admin_id}:
            data = {}  # Explicit background-job authors must not inherit another actor's identity.
        for field, value in data.items():
            if not getattr(row, field) or field == "transport":
                setattr(row, field, value)
        if row.admin_id and not row.actor_username:
            admin = session.get(Admin, row.admin_id)
            if admin:
                row.actor_username, row.actor_name = admin.username, admin.display_name
        if not row.actor_username and row.admin_id is None:
            row.actor_username = "系统" if row.transport == "system" else "未认证"
        row.detail = redact(row.detail)


def record(session: Session, action: str, *, details: Any = None, **fields: Any) -> None:
    session.add(AuditLog(action=action, detail=redact(details or {}), **fields))
    session.commit()


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
