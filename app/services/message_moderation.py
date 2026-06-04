import re
from typing import Any, Protocol

from nonebot import logger
from sqlmodel import Session, col, select

from app.models import MessageModerationRule
from app.models.entities import MessageModerationAction
from app.services import cloud_text_moderation
from app.services import onebot
from app.services.tencentcloud_tms_config import get_tms_config


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
        select(MessageModerationRule)
        .where(
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


def _extract_image_urls(event: GroupMessageLike) -> list[str]:
    """从消息事件中提取所有图片的 URL。"""
    urls: list[str] = []
    message = getattr(event, "message", None)
    if message is None:
        return urls
    
    logger.info(f"正在解析消息段提取图片: {message}")
    # NoneBot2 OneBot v11 Message 对象可迭代，每个 MessageSegment 有 type 和 data
    try:
        for seg in message:
            seg_type = getattr(seg, "type", None) or (seg.get("type") if isinstance(seg, dict) else None)
            seg_data = getattr(seg, "data", None) or (seg.get("data") if isinstance(seg, dict) else None)
            logger.info(f"消息段 type={seg_type}, data={seg_data}")
            if seg_type == "image" and seg_data:
                url = seg_data.get("url") or seg_data.get("file")
                logger.info(f"提取到图片字段: {url}")
                if url and isinstance(url, str) and url.startswith("http"):
                    urls.append(url)
    except (TypeError, AttributeError) as e:
        logger.warning(f"提取图片报错: {e}")
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


async def _apply_cloud_review_if_needed(
    rule: MessageModerationRule, session: Session, text: str,
    group_id: int, user_id: int, message_id: int,
) -> bool:
    """如果规则开启了云审核，执行云审核并返回是否应触发动作。未开启云审核则直接返回 True。"""
    if not rule.cloud_review_enabled:
        return True
    config = get_tms_config(session)
    decision = await cloud_text_moderation.moderate_text(
        config,
        text,
        group_id=group_id,
        user_id=user_id,
        message_id=message_id,
    )
    return decision.should_trigger


async def moderate_group_message(session: Session, event: GroupMessageLike) -> MessageModerationRule | None:
    # ── 阶段 1：纯文本正则匹配 ──
    message_text = event.get_plaintext()
    if message_text:
        rule = find_matching_moderation_rule(session, event.group_id, message_text)
        if rule:
            should_trigger = await _apply_cloud_review_if_needed(
                rule, session, message_text,
                event.group_id, event.user_id, event.message_id,
            )
            if should_trigger:
                await apply_moderation_action(rule, event.group_id, event.user_id, event.message_id)
                return rule
            return None

    # ── 阶段 2：图片 OCR 识别 + 正则匹配 ──
    if not _has_ocr_enabled_rule(session, event.group_id):
        return None

    logger.info("当前群存在启用了 OCR 的规则，准备提取图片...")
    image_urls = _extract_image_urls(event)
    logger.info(f"最终提取到的合法图片 URL: {image_urls}")
    
    if not image_urls:
        return None

    # 延迟导入，避免未安装 paddleocr 时影响其他功能
    from app.services.ocr import ocr_image_from_url

    for url in image_urls:
        try:
            ocr_text = await ocr_image_from_url(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"OCR 识别失败 (url={url}): {exc}")
            continue
        if not ocr_text:
            logger.warning(f"图片中未提取到文字或文字过小被过滤 (url={url})")
            continue
        logger.info(f"OCR 识别结果 (group={event.group_id}, user={event.user_id}): {ocr_text[:200]}")
        rule = _find_matching_ocr_rule(session, event.group_id, ocr_text)
        if rule:
            should_trigger = await _apply_cloud_review_if_needed(
                rule, session, ocr_text,
                event.group_id, event.user_id, event.message_id,
            )
            if should_trigger:
                await apply_moderation_action(rule, event.group_id, event.user_id, event.message_id)
                return rule
    return None
