from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import TencentCloudTmsConfig
from app.schemas.admin import TencentCloudTmsConfigIn, TencentCloudTmsConfigOut


def get_tms_config(session: Session) -> TencentCloudTmsConfig:
    config = session.exec(select(TencentCloudTmsConfig)).first()
    if config:
        return config
    config = TencentCloudTmsConfig()
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


def update_tms_config(
    session: Session, payload: TencentCloudTmsConfigIn
) -> TencentCloudTmsConfig:
    config = get_tms_config(session)
    config.secret_id = payload.secret_id.strip()
    if payload.secret_key:
        config.secret_key = payload.secret_key.strip()
    config.region = payload.region.strip() or "ap-guangzhou"
    config.biz_type = payload.biz_type.strip() or "TencentCloudDefault"
    config.source_language = payload.source_language.strip() or "zh"
    config.timeout_seconds = payload.timeout_seconds
    config.updated_at = datetime.now(timezone.utc)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


def tms_config_out(config: TencentCloudTmsConfig) -> TencentCloudTmsConfigOut:
    return TencentCloudTmsConfigOut(
        secret_id=config.secret_id,
        secret_key_configured=bool(config.secret_key),
        region=config.region,
        biz_type=config.biz_type,
        source_language=config.source_language,
        timeout_seconds=config.timeout_seconds,
    )
