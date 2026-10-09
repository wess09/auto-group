from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import ImageReviewConfig
from app.schemas.admin import ImageReviewConfigIn, ImageReviewConfigOut


def get_image_review_config(session: Session) -> ImageReviewConfig:
    config = session.exec(select(ImageReviewConfig)).first()
    # A missing configuration is disabled; reading it does not create a row.
    return config or ImageReviewConfig()


def image_review_config_out(config: ImageReviewConfig) -> ImageReviewConfigOut:
    channels = [
        {
            **{key: value for key, value in channel.items() if key != "api_key"},
            "api_key_configured": bool(channel.get("api_key")),
        }
        for channel in config.channels
    ]
    return ImageReviewConfigOut(
        enabled=config.enabled,
        system_prompt=config.system_prompt,
        min_confidence=config.min_confidence,
        channels=channels,
    )


def update_image_review_config(session: Session, payload: ImageReviewConfigIn) -> ImageReviewConfig:
    config = get_image_review_config(session)
    previous_keys = {channel["id"]: channel.get("api_key", "") for channel in config.channels}
    channels = []
    for channel in payload.channels:
        data = channel.model_dump(exclude={"clear_api_key"})
        data["api_key"] = (
            "" if channel.clear_api_key else channel.api_key or previous_keys.get(channel.id, "")
        )
        channels.append(data)
    config.enabled = payload.enabled
    config.system_prompt = payload.system_prompt
    config.min_confidence = payload.min_confidence
    config.channels = channels
    config.updated_at = datetime.now(timezone.utc)
    session.add(config)
    session.flush()
    return config
