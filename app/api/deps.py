from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.core.security import decode_access_token
from app.models import Admin


SessionDep = Annotated[Session, Depends(get_session)]


def get_current_admin(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Admin:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效") from exc
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")
    admin = session.exec(select(Admin).where(Admin.username == username)).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="管理员不存在")
    return admin


AdminDep = Annotated[Admin, Depends(get_current_admin)]
