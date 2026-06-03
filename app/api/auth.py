from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models import Admin
from app.schemas.admin import LoginIn, TokenOut
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
    clear_login_failures(rate_limit_keys)
    return TokenOut(access_token=create_access_token(admin.username))
