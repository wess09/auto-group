from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from app.api.deps import AdminDep, SessionDep
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models import Admin
from app.schemas.admin import LoginIn, TokenOut, TotpCodeIn
from app.services.totp import new_secret, provisioning_uri, verify_totp
from app.services.auth_rate_limit import (
    LoginRateLimitExceeded,
    assert_login_allowed,
    clear_login_failures,
    login_rate_limit_keys,
    record_login_failure,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, session: SessionDep) -> TokenOut:
    settings = get_settings()
    rate_limit_keys = login_rate_limit_keys(payload.username, request, settings)
    try:
        assert_login_allowed(rate_limit_keys, settings)
    except LoginRateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录失败次数过多，请 {exc.retry_after_seconds} 秒后再试",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    admin = session.exec(select(Admin).where(Admin.username == payload.username)).first()
    if not admin or not verify_password(payload.password, admin.password_hash):
        record_login_failure(rate_limit_keys, settings)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if admin.totp_enabled and not verify_totp(admin.totp_secret, payload.totp_code):
        record_login_failure(rate_limit_keys, settings)
        raise HTTPException(status_code=401, detail="动态验证码错误或未填写")
    clear_login_failures(rate_limit_keys)
    return TokenOut(access_token=create_access_token(admin.username))


@router.get("/2fa/status")
def totp_status(admin: AdminDep) -> dict[str, bool]:
    return {"enabled": admin.totp_enabled}


@router.post("/2fa/setup")
def totp_setup(admin: AdminDep, session: SessionDep) -> dict[str, str]:
    if admin.totp_enabled:
        raise HTTPException(status_code=409, detail="双因素认证已启用")
    admin.totp_secret = new_secret()
    session.add(admin)
    session.commit()
    return {
        "secret": admin.totp_secret,
        "otpauth_uri": provisioning_uri(admin.totp_secret, admin.username),
    }


@router.post("/2fa/enable")
def totp_enable(payload: TotpCodeIn, admin: AdminDep, session: SessionDep) -> dict[str, bool]:
    if not admin.totp_secret or not verify_totp(admin.totp_secret, payload.code):
        raise HTTPException(status_code=400, detail="验证码无效")
    admin.totp_enabled = True
    session.add(admin)
    session.commit()
    return {"enabled": True}


@router.post("/2fa/disable")
def totp_disable(payload: TotpCodeIn, admin: AdminDep, session: SessionDep) -> dict[str, bool]:
    if not admin.totp_enabled or not verify_totp(admin.totp_secret, payload.code):
        raise HTTPException(status_code=400, detail="验证码无效")
    admin.totp_enabled = False
    admin.totp_secret = ""
    session.add(admin)
    session.commit()
    return {"enabled": False}
