from fastapi import APIRouter

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.schemas.admin import PublicGroupOut
from app.services.groups import get_recommended_group


router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/recommended-group", response_model=PublicGroupOut)
def recommended_group(session: SessionDep) -> PublicGroupOut:
    settings = get_settings()
    group = get_recommended_group(session, require_join_url=True)
    if not group:
        return PublicGroupOut(available=False, message=settings.public_fallback_message)
    return PublicGroupOut(
        available=True,
        group_id=group.group_id,
        group_name=group.name or str(group.group_id),
        join_url=group.join_url,
        current_members=group.current_members,
        max_members=group.max_members,
        message=f"推荐加入 {group.name or group.group_id}",
    )
