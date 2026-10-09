import re
from typing import Any, Protocol

from nonebot import logger
from sqlmodel import Session, col, select

from app.models import ImageReviewConfig, MessageModerationRule, TencentCloudTmsConfig
from app.models.entities import MessageModerationAction
from app.services import cloud_text_moderation, image_moderation
from app.services import onebot


class GroupMessageLike(Protocol):
    group_id: int
    user_id: int
    message_id: int
    message: Any  # 消息段列表，用于提取图片

    def get_plaintext(self) -> str: ...


def message_matches_rule(rule: MessageModerationRule, message_text: str) -> bool:
    for pattern in rule.patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        try:
            if re.search(pattern, message_text, flags=re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def find_matching_moderation_rule(
    session: Session, group_id: int, message_text: str
) -> MessageModerationRule | None:
    rules = session.exec(
        select(MessageModerationRule)
        .where(col(MessageModerationRule.enabled) == True)  # noqa: E712
        .order_by(col(MessageModerationRule.group_id).desc(), col(MessageModerationRule.id).desc())
    ).all()
    for rule in rules:
        if rule.group_id is not None and rule.group_id != group_id:
            continue
        if message_matches_rule(rule, message_text):
            return rule
    return None


def _has_ocr_enabled_rule(session: Session, group_id: int) -> bool:
    """检查是否存在适用于该群的、已启用 OCR 的审查规则。"""
    rules = session.exec(
        select(MessageModerationRule).where(
            col(MessageModerationRule.enabled) == True,  # noqa: E712
            col(MessageModerationRule.ocr_enabled) == True,  # noqa: E712
        )
    ).all()
    for rule in rules:
        if rule.group_id is None or rule.group_id == group_id:
            return True
    return False


def _find_matching_ocr_rule(
    session: Session, group_id: int, ocr_text: str
) -> MessageModerationRule | None:
    """在启用 OCR 的规则中查找匹配的规则。"""
    rules = session.exec(
        select(MessageModerationRule)
        .where(
            col(MessageModerationRule.enabled) == True,  # noqa: E712
            col(MessageModerationRule.ocr_enabled) == True,  # noqa: E712
        )
        .order_by(col(MessageModerationRule.group_id).desc(), col(MessageModerationRule.id).desc())
    ).all()
    for rule in rules:
        if rule.group_id is not None and rule.group_id != group_id:
            continue
        if message_matches_rule(rule, ocr_text):
            return rule
    return None


def has_image_segments(event: GroupMessageLike) -> bool:
    """Also identify image segments whose URL is unavailable."""
    return any(
        (getattr(seg, "type", None) or (seg.get("type") if isinstance(seg, dict) else None))
        == "image"
        for seg in (getattr(event, "message", None) or [])
    )


def message_context(event: GroupMessageLike) -> str:
    return f"group={event.group_id}, user={event.user_id}, message={event.message_id}"


def _extract_image_urls(event: GroupMessageLike) -> list[str]:
    """从消息事件中提取所有图片的 URL。"""
    urls: list[str] = []
    message = getattr(event, "message", None)
    if message is None:
        return urls

    # NoneBot2 OneBot v11 Message 对象可迭代，每个 MessageSegment 有 type 和 data
    try:
        for seg in message:
            seg_type = getattr(seg, "type", None) or (
                seg.get("type") if isinstance(seg, dict) else None
            )
            seg_data = getattr(seg, "data", None) or (
                seg.get("data") if isinstance(seg, dict) else None
            )
            if seg_type == "image" and seg_data:
                url = seg_data.get("url") or seg_data.get("file")
                if (
                    url
                    and isinstance(url, str)
                    and url.startswith(("https://", "http://", "data:image/"))
                ):
                    if url not in urls:
                        urls.append(url)
    except (TypeError, AttributeError) as exc:
        logger.warning(f"提取图片失败（{message_context(event)}）：{type(exc).__name__}")
    return urls


async def apply_moderation_action(
    rule: MessageModerationRule, group_id: int, user_id: int, message_id: int
) -> None:
    errors: list[str] = []
    if rule.action in {
        MessageModerationAction.recall,
        MessageModerationAction.recall_and_mute,
    }:
        try:
            await onebot.delete_msg(message_id)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"撤回失败：{exc}")
    if rule.action in {
        MessageModerationAction.mute,
        MessageModerationAction.recall_and_mute,
    }:
        try:
            await onebot.set_group_ban(group_id, user_id, rule.mute_duration_seconds)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"禁言失败：{exc}")
    if errors:
        raise RuntimeError("；".join(errors))


async def _moderate_snapshot(
    event: GroupMessageLike, rows: list[dict], config_data: dict, image_config_data: dict
) -> MessageModerationRule | None:
    has_images = has_image_segments(event)
    context = message_context(event)
    rules = [MessageModerationRule(**row) for row in rows]
    config = TencentCloudTmsConfig(**config_data)
    image_config = ImageReviewConfig(**image_config_data)

    async def apply(rule: MessageModerationRule, text: str) -> bool:
        if rule.cloud_review_enabled:
            decision = await cloud_text_moderation.moderate_text(
                config,
                text,
                group_id=event.group_id,
                user_id=event.user_id,
                message_id=event.message_id,
            )
            if not decision.should_trigger:
                return False
        await apply_moderation_action(rule, event.group_id, event.user_id, event.message_id)
        return True

    message_text = event.get_plaintext()
    for rule in rules:
        if message_text and message_matches_rule(rule, message_text):
            if await apply(rule, message_text):
                if has_images:
                    logger.info(f"图片审核跳过（{context}）：文本规则已执行动作，rule={rule.id}")
                return rule
            break

    ocr_rules = [rule for rule in rules if rule.ocr_enabled]
    image_rule = next((rule for rule in rules if rule.image_review_enabled), None)
    if has_images and not image_rule:
        logger.info(
            f"图片审核跳过（{context}）：消息审查中没有对当前群生效且已启用"
            "「LLM 多模态图片审核」的规则"
        )
    if not ocr_rules and not image_rule:
        return None
    image_urls = _extract_image_urls(event)
    if not image_urls:
        if has_images and image_rule:
            logger.warning(f"图片审核跳过（{context}）：图片消息没有可用的图片 URL")
        return None
    if ocr_rules:
        from app.services.ocr import ocr_image_from_url

        for url in image_urls:
            try:
                text = await ocr_image_from_url(url)
            except Exception as exc:
                logger.warning(f"OCR 识别失败：{type(exc).__name__}")
                continue
            for rule in ocr_rules:
                if text and message_matches_rule(rule, text):
                    if await apply(rule, text):
                        if image_rule:
                            logger.info(
                                f"图片审核跳过（{context}）：OCR 规则已执行动作，rule={rule.id}"
                            )
                        return rule
                    break

    # Vision review is independent of regex/OCR/cloud text review.
    if image_rule and image_config.enabled:
        logger.info(
            f"图片审核开始（{context}）：rule={image_rule.id}，图片数={len(image_urls)}，"
            f"最低置信度={image_config.min_confidence}"
        )
        for index, url in enumerate(image_urls, start=1):
            image_context = f"{context}, image={index}/{len(image_urls)}"
            verdict = await image_moderation.review_image(
                image_config, url, message_text, context=image_context
            )
            if verdict is None:
                logger.warning(f"图片审核失败（{image_context}）：没有有效审核结果，跳过处理")
                continue
            trigger = verdict.violates and verdict.confidence >= image_config.min_confidence
            logger.info(
                f"图片审核完成（{image_context}, channel={verdict._channel_name}, "
                f"model={verdict._model_name}）："
                f"违规={verdict.violates}，"
                f"置信度={verdict.confidence}，触发动作={trigger}，原因={verdict.reason!r}"
            )
            if trigger:
                logger.info(
                    f"图片审核执行动作（{image_context}）：rule={image_rule.id}，"
                    f"action={image_rule.action.value}"
                )
                try:
                    await apply_moderation_action(
                        image_rule, event.group_id, event.user_id, event.message_id
                    )
                except Exception as exc:
                    logger.error(
                        f"图片审核动作失败（{image_context}）：action={image_rule.action.value}，"
                        f"{type(exc).__name__}"
                    )
                    raise
                logger.info(
                    f"图片审核动作完成（{image_context}）：action={image_rule.action.value}，"
                    "结束本条消息的审核"
                )
                return image_rule
            reason = "模型判定不违规" if not verdict.violates else "置信度未达到阈值"
            logger.info(f"图片审核不执行动作（{image_context}）：{reason}")
    elif image_rule:
        logger.warning(f"图片审核跳过（{context}）：全局图片审核服务未启用")
    return None


async def moderate_group_message(
    session: Session, event: GroupMessageLike
) -> MessageModerationRule | None:
    from app.services.admin.bot_data import moderation_snapshot

    snapshot = moderation_snapshot(session, event.group_id)
    return await _moderate_snapshot(event, *snapshot)


async def moderate_group_message_detached(event: GroupMessageLike) -> MessageModerationRule | None:
    """Use a detached configuration snapshot during network/OCR calls."""
    from app.services.admin.bot_data import moderation_snapshot
    from app.services.admin.runtime import database

    snapshot = await database(moderation_snapshot, event.group_id)
    return await _moderate_snapshot(event, *snapshot)
