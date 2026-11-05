from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from app.core.database import get_session
from app.models import Admin
from app.services.admin_accounts import resolve_token


SessionDep = Annotated[Session, Depends(get_session)]


def get_current_admin(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Admin:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    token = authorization.removeprefix("Bearer ").strip()
    return resolve_token(session, token)


AdminDep = Annotated[Admin, Depends(get_current_admin)]
