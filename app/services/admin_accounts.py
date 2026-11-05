import threading

from fastapi import HTTPException
from sqlalchemy import update as sql_update
from sqlmodel import Session, select

from app.core.security import decode_access_token, hash_password
from app.models import Admin, AuditLog
from app.models.entities import now_utc
from app.schemas.admin import AdminCreateIn, AdminPasswordIn, AdminProfile, AdminUpdateIn


write_lock = threading.Lock()


def resolve_token(session: Session, token: str) -> Admin:
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(401, "登录已失效") from exc
    admin = session.exec(select(Admin).where(Admin.username == payload.get("sub"))).first()
    if (
        not admin
        or not admin.enabled
        or payload.get("ver", 0) != admin.token_version
        or payload.get("aid", admin.id) != admin.id
    ):
        raise HTTPException(401, "账号已停用或登录已失效，请重新登录")
    return admin


def profile(session: Session, token: str) -> AdminProfile:
    return AdminProfile.model_validate(resolve_token(session, token))


def require_superadmin(session: Session, admin_id: int) -> Admin:
    admin = session.get(Admin, admin_id)
    if not admin or not admin.enabled:
        raise HTTPException(401, "登录已失效")
    if admin.role != "superadmin":
        raise HTTPException(403, "只有超级管理员可以管理后台账号")
    return admin


def invalidate(session: Session, admin: Admin) -> None:
    admin.updated_at = now_utc()
    session.add(admin)
    session.flush()
    # Increment in SQL so concurrent password/logout requests cannot lose a revocation.
    session.exec(
        sql_update(Admin).where(Admin.id == admin.id).values(token_version=Admin.token_version + 1)
    )
    session.refresh(admin, attribute_names=["token_version"])
    session.info.setdefault("revoke_admin_ids", set()).add(admin.id)


def create(session: Session, params: AdminCreateIn, actor_id: int) -> AdminProfile:
    with write_lock:
        require_superadmin(session, actor_id)
        row = Admin(
            username=params.username,
            password_hash=hash_password(params.password.get_secret_value()),
            display_name=params.display_name,
            role=params.role,
        )
        session.add(row)
        session.flush()
        session.add(
            AuditLog(
                admin_id=actor_id,
                action="admins.create",
                target=str(row.id),
                detail={"after": AdminProfile.model_validate(row).model_dump(mode="json")},
            )
        )
        session.commit()
        session.refresh(row)
        return AdminProfile.model_validate(row)


def update(session: Session, params: AdminUpdateIn, actor_id: int) -> AdminProfile:
    with write_lock:
        require_superadmin(session, actor_id)
        row = session.get(Admin, params.id)
        if row is None:
            raise HTTPException(404, "管理员不存在")
        data = params.model_dump(exclude_unset=True, exclude={"id"})
        if any(value is None for value in data.values()):
            raise HTTPException(422, "字段不能为空")
        if row.id == actor_id and (
            data.get("enabled") is False or data.get("role", row.role) != row.role
        ):
            raise HTTPException(409, "不能停用或降级当前登录账号，请使用另一个超级管理员操作")
        if (
            row.enabled
            and row.role == "superadmin"
            and (data.get("enabled") is False or data.get("role", row.role) != "superadmin")
        ):
            others = session.exec(
                select(Admin.id).where(
                    Admin.enabled == True,  # noqa: E712
                    Admin.role == "superadmin",
                    Admin.id != row.id,
                )
            ).first()
            if others is None:
                raise HTTPException(409, "必须保留至少一个启用的超级管理员")
        before = AdminProfile.model_validate(row).model_dump(mode="json")
        if any(
            getattr(row, key) != value for key, value in data.items() if key in {"enabled", "role"}
        ):
            invalidate(session, row)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = now_utc()
        session.add(row)
        session.add(
            AuditLog(
                admin_id=actor_id,
                action="admins.update",
                target=str(row.id),
                detail={
                    "before": before,
                    "after": AdminProfile.model_validate(row).model_dump(mode="json"),
                },
            )
        )
        session.commit()
        session.refresh(row)
        return AdminProfile.model_validate(row)


def reset_password(session: Session, params: AdminPasswordIn, actor_id: int) -> dict:
    with write_lock:
        require_superadmin(session, actor_id)
        row = session.get(Admin, params.id)
        if row is None:
            raise HTTPException(404, "管理员不存在")
        row.password_hash = hash_password(params.password.get_secret_value())
        invalidate(session, row)
        session.add(
            AuditLog(
                admin_id=actor_id,
                action="admins.reset-password",
                target=str(row.id),
                detail={"username": row.username},
            )
        )
        session.commit()
        return {"ok": True}


def reset_totp(session: Session, item_id: int, actor_id: int) -> dict:
    with write_lock:
        require_superadmin(session, actor_id)
        row = session.get(Admin, item_id)
        if row is None:
            raise HTTPException(404, "管理员不存在")
        before = row.totp_enabled
        row.totp_enabled, row.totp_secret = False, ""
        invalidate(session, row)
        session.add(
            AuditLog(
                admin_id=actor_id,
                action="admins.reset-2fa",
                target=str(row.id),
                detail={"username": row.username, "previously_enabled": before},
            )
        )
        session.commit()
        return {"ok": True}
