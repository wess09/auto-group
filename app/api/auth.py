from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from app.api.deps import AdminDep, SessionDep
from app.api.audited_route import AuditedRoute
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Admin
from app.models.entities import now_utc
from app.schemas.admin import AdminProfile, LoginIn, PasswordChangeIn, TokenOut, TotpCodeIn
from app.services import audit
from app.services.admin_accounts import invalidate
from app.services.totp import new_secret, provisioning_uri, verify_totp
from app.services.auth_rate_limit import (
    LoginRateLimitExceeded,
    assert_login_allowed,
    clear_login_failures,
    login_rate_limit_keys,
    record_login_failure,
)


router = APIRouter(prefix="/api/auth", tags=["auth"], route_class=AuditedRoute)


def log_event(session, request, action, admin=None, *, username="", status="success", details=None):
    if admin is not None:
        request.state.audit_actor = AdminProfile.model_validate(admin)
    fields = audit.request_context(admin, request)
    if not admin:
        fields["actor_username"] = username[:64]
    audit.record(
        session,
        action,
        target=str(admin.id) if admin else username[:64],
        status=status,
        details=details,
        **fields,
    )


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, session: SessionDep) -> TokenOut:
    settings = get_settings()
    rate_limit_keys = login_rate_limit_keys(payload.username, request, settings)
    try:
        assert_login_allowed(rate_limit_keys, settings)
    except LoginRateLimitExceeded as exc:
        log_event(
            session,
            request,
            "auth.login",
            username=payload.username,
            status="failed",
            details={"reason": "rate_limited"},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录失败次数过多，请 {exc.retry_after_seconds} 秒后再试",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    admin = session.exec(select(Admin).where(Admin.username == payload.username.strip())).first()
    if not admin or not admin.enabled or not verify_password(payload.password, admin.password_hash):
        record_login_failure(rate_limit_keys, settings)
        log_event(
            session,
            request,
            "auth.login",
            admin,
            username=payload.username,
            status="failed",
            details={"reason": "invalid_credentials_or_disabled"},
        )
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if admin.totp_enabled and not verify_totp(admin.totp_secret, payload.totp_code):
        record_login_failure(rate_limit_keys, settings)
        log_event(
            session,
            request,
            "auth.login",
            admin,
            status="failed",
            details={"reason": "invalid_totp"},
        )
        raise HTTPException(status_code=401, detail="动态验证码错误或未填写")
    clear_login_failures(rate_limit_keys)
    admin.last_login_at = now_utc()
    admin.last_login_ip = audit.request_context(admin, request)["client_ip"]
    session.add(admin)
    log_event(session, request, "auth.login", admin)
    return TokenOut(
        access_token=create_access_token(
            admin.username, {"aid": admin.id, "ver": admin.token_version}
        )
    )


@router.get("/me", response_model=AdminProfile)
def current_account(admin: AdminDep) -> AdminProfile:
    return AdminProfile.model_validate(admin)


@router.post("/logout")
def logout(admin: AdminDep, request: Request, session: SessionDep) -> dict[str, bool]:
    invalidate(session, admin)
    log_event(session, request, "auth.logout", admin)
    return {"ok": True}


@router.post("/password")
def change_password(
    payload: PasswordChangeIn, admin: AdminDep, request: Request, session: SessionDep
) -> dict[str, bool]:
    if not verify_password(payload.current_password.get_secret_value(), admin.password_hash) or (
        admin.totp_enabled and not verify_totp(admin.totp_secret, payload.totp_code)
    ):
        log_event(
            session,
            request,
            "auth.change-password",
            admin,
            status="failed",
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(400, "当前密码或动态验证码错误")
    admin.password_hash = hash_password(payload.new_password.get_secret_value())
    invalidate(session, admin)
    log_event(session, request, "auth.change-password", admin)
    return {"ok": True}


@router.get("/2fa/status")
def totp_status(admin: AdminDep) -> dict[str, bool]:
    return {"enabled": admin.totp_enabled}


@router.post("/2fa/setup")
def totp_setup(admin: AdminDep, request: Request, session: SessionDep) -> dict[str, str]:
    if admin.totp_enabled:
        raise HTTPException(status_code=409, detail="双因素认证已启用")
    admin.totp_secret = new_secret()
    session.add(admin)
    log_event(session, request, "auth.2fa.setup", admin)
    return {
        "secret": admin.totp_secret,
        "otpauth_uri": provisioning_uri(admin.totp_secret, admin.username),
    }


@router.post("/2fa/enable")
def totp_enable(
    payload: TotpCodeIn, admin: AdminDep, request: Request, session: SessionDep
) -> dict[str, bool]:
    if not admin.totp_secret or not verify_totp(admin.totp_secret, payload.code):
        log_event(session, request, "auth.2fa.enable", admin, status="failed")
        raise HTTPException(status_code=400, detail="验证码无效")
    admin.totp_enabled = True
    invalidate(session, admin)
    log_event(session, request, "auth.2fa.enable", admin)
    return {"enabled": True}


@router.post("/2fa/disable")
def totp_disable(
    payload: TotpCodeIn, admin: AdminDep, request: Request, session: SessionDep
) -> dict[str, bool]:
    if not admin.totp_enabled or not verify_totp(admin.totp_secret, payload.code):
        log_event(session, request, "auth.2fa.disable", admin, status="failed")
        raise HTTPException(status_code=400, detail="验证码无效")
    admin.totp_enabled = False
    admin.totp_secret = ""
    invalidate(session, admin)
    log_event(session, request, "auth.2fa.disable", admin)
    return {"enabled": False}
