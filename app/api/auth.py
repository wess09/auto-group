from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import create_access_token, verify_password
from app.models import Admin
from app.schemas.admin import LoginIn, TokenOut


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, session: SessionDep) -> TokenOut:
    admin = session.exec(select(Admin).where(Admin.username == payload.username)).first()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return TokenOut(access_token=create_access_token(admin.username))
