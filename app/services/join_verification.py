"""Persistent, per-member image challenges. Database transactions never cross an await."""

import asyncio
import base64
import hashlib
import hmac
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Protocol

from captcha.image import ImageCaptcha
from nonebot import logger
from sqlalchemy import delete
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import AuditLog, ManagedGroup
from app.models.entities import JoinVerification, JoinVerificationMessage, now_utc
from app.services.admin.runtime import database
from app.services.onebot import BotLike


CAPTCHA_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CAPTCHA_LENGTH = 5
CAPTCHA_LIFETIME_SECONDS = 600
MUTE_SECONDS = (10, 20, 30)
REFRESH_COMMAND = "/验证码"
Key = tuple[str, int, int]


class VerificationBot(BotLike, Protocol):
    self_id: str


@lru_cache(maxsize=1)
def _locks(loop: asyncio.AbstractEventLoop) -> list[asyncio.Lock]:
    # Bounded memory; locks are recreated when the application's event loop changes.
    return [asyncio.Lock() for _ in range(64)]


def _lock(key: Key) -> asyncio.Lock:
    return _locks(asyncio.get_running_loop())[hash(key) % 64]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def normalize_answer(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split()).upper()


def answer_hash(salt: str, text: str) -> str:
    return hashlib.sha256(f"{salt}:{normalize_answer(text)}".encode()).hexdigest()


def generate_captcha() -> tuple[str, bytes]:
    answer = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(CAPTCHA_LENGTH))
    png = ImageCaptcha(width=240, height=90).generate(answer).getvalue()
    return answer, png


def _find(session: Session, key: Key) -> JoinVerification | None:
    bot_id, group_id, user_id = key
    return session.exec(
        select(JoinVerification).where(
            JoinVerification.bot_id == bot_id,
            JoinVerification.group_id == group_id,
            JoinVerification.user_id == user_id,
        )
    ).first()


def _enabled(session: Session, group_id: int) -> bool:
    group = session.exec(select(ManagedGroup).where(ManagedGroup.group_id == group_id)).first()
    return bool(group and group.enabled and group.join_verification_enabled)


def _audit(session: Session, row: JoinVerification, action: str, **detail: Any) -> None:
    session.add(
        AuditLog(
            action=f"verification.{action}",
            target=str(row.user_id),
            detail={
                "bot_id": row.bot_id,
                "group_id": row.group_id,
                "wrong_attempts": row.wrong_attempts,
                **detail,
            },
        )
    )


def prepare_join(session: Session, key: Key, event_time: int) -> int | None:
    if not _enabled(session, key[1]):
        return None
    row = _find(session, key)
    if row and event_time <= row.joined_event_time:
        return None
    if row:
        session.exec(
            delete(JoinVerificationMessage).where(JoinVerificationMessage.verification_id == row.id)
        )
    else:
        row = JoinVerification(
            bot_id=key[0], group_id=key[1], user_id=key[2], joined_event_time=event_time
        )
    row.joined_event_time = event_time
    row.status, row.delivered, row.wrong_attempts = "pending", False, 0
    row.answer_hash, row.salt, row.retry_after = "", "", None
    row.updated_at = now_utc()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row.id


def install_challenge(session: Session, item_id: int, salt: str, digest: str) -> None:
    row = session.get(JoinVerification, item_id)
    if row and row.status == "pending":
        row.salt, row.answer_hash, row.delivered = salt, digest, False
        row.expires_at = now_utc() + timedelta(seconds=CAPTCHA_LIFETIME_SECONDS)
        row.updated_at = now_utc()
        session.add(row)
        session.commit()


def record_action(session: Session, item_id: int, action: str, error: str = "") -> None:
    row = session.get(JoinVerification, item_id)
    if row is None:
        return
    if action == "challenge":
        row.delivered = not error
    elif action == "kick" and not error and row.status == "kick_pending":
        row.status = "kicked"
        row.answer_hash, row.salt = "", ""
    row.updated_at = now_utc()
    session.add(row)
    _audit(session, row, action, success=not error, error=error)
    session.commit()


def leave_group(session: Session, key: Key, event_time: int) -> None:
    rows = (
        session.exec(
            select(JoinVerification).where(
                JoinVerification.bot_id == key[0], JoinVerification.group_id == key[1]
            )
        ).all()
        if key[0] == str(key[2])
        else [_find(session, key)]
    )
    for row in rows:
        if (
            row
            and event_time >= row.joined_event_time
            and row.status in {"pending", "kick_pending"}
        ):
            row.status = "left"
            row.answer_hash, row.salt = "", ""
            row.updated_at = now_utc()
            session.add(row)
    session.commit()


def consume_message(
    session: Session, key: Key, message_id: int, event_time: int, text: str
) -> dict[str, Any]:
    row = _find(session, key)
    if row is None or row.status not in {"pending", "kick_pending"}:
        return {"action": "ignore"}
    if not _enabled(session, key[1]):
        row.status, row.answer_hash, row.salt = "cancelled", "", ""
        session.add(row)
        session.commit()
        return {"action": "ignore"}
    result: dict[str, Any] = {"id": row.id, "action": "waiting"}
    if event_time < row.joined_event_time:
        return result
    if (
        session.exec(
            select(JoinVerificationMessage.id).where(
                JoinVerificationMessage.verification_id == row.id,
                JoinVerificationMessage.message_id == message_id,
            )
        ).first()
        is not None
    ):
        return result
    session.add(JoinVerificationMessage(verification_id=row.id, message_id=message_id))
    now = now_utc()
    if row.status == "kick_pending":
        result["action"] = "kick"
    elif row.retry_after and (
        now < _utc(row.retry_after) or event_time + 1 <= _utc(row.retry_after).timestamp()
    ):
        pass  # Cooldown messages never count as another attempt, including delayed reports.
    elif not row.delivered or now >= _utc(row.expires_at) or text.strip() == REFRESH_COMMAND:
        result["action"] = "refresh"
    elif not text.strip():
        pass  # Stickers, files and other messages without text are not answers.
    elif hmac.compare_digest(row.answer_hash, answer_hash(row.salt, text[:500])):
        row.status, row.answer_hash, row.salt = "verified", "", ""
        result["action"] = "passed"
        _audit(session, row, "passed")
    else:
        row.wrong_attempts += 1
        _audit(session, row, "wrong_answer")
        if row.wrong_attempts > len(MUTE_SECONDS):
            row.status = "kick_pending"
            result["action"] = "kick"
        else:
            seconds = MUTE_SECONDS[row.wrong_attempts - 1]
            row.retry_after = now + timedelta(seconds=seconds)
            result.update(action="mute", seconds=seconds, wrong_attempts=row.wrong_attempts)
    row.updated_at = now
    session.add(row)
    session.commit()
    return result


async def _api(bot: VerificationBot, api: str, **data: Any) -> str:
    timeout = get_settings().onebot_api_timeout_seconds
    try:
        await asyncio.wait_for(bot.call_api(api, **data, _timeout=timeout), timeout=timeout)
        return ""
    except Exception as exc:
        error = type(exc).__name__
        logger.warning(
            f"入群验证接口失败：bot={bot.self_id}, group={data.get('group_id')}, "
            f"api={api}, error={error}"
        )
        return error


async def _send(bot: VerificationBot, key: Key, text: str, png: bytes | None = None) -> str:
    message = [
        {"type": "at", "data": {"qq": str(key[2])}},
        {"type": "text", "data": {"text": " " + text}},
    ]
    if png is not None:
        message.append(
            {"type": "image", "data": {"file": "base64://" + base64.b64encode(png).decode()}}
        )
    return await _api(bot, "send_group_msg", group_id=key[1], message=message)


async def _challenge(bot: VerificationBot, key: Key, item_id: int, welcome: bool = False) -> None:
    answer, png = await asyncio.to_thread(generate_captcha)
    salt = secrets.token_hex(16)
    await database(install_challenge, item_id, salt, answer_hash(salt, answer))
    text = ("欢迎加入本群！\n" if welcome else "已刷新验证码，答错次数保留。\n") + (
        "请直接在群内回复图片中的 5 位验证码（不区分大小写），有效期 10 分钟。\n"
        "答错第 1/2/3 次分别禁言 10/20/30 秒，第 4 次踢出；禁言结束后再作答。\n"
        f"看不清可发送 {REFRESH_COMMAND} 换图。"
    )
    error = await _send(bot, key, text, png)
    await database(record_action, item_id, "challenge", error)


async def handle_notice(bot: VerificationBot, event: Any) -> None:
    notice_type = getattr(event, "notice_type", "")
    if notice_type not in {"group_increase", "group_decrease"}:
        return
    group_id, user_id = int(event.group_id), int(event.user_id)
    if group_id <= 0 or user_id <= 0:
        return
    key = (str(bot.self_id), group_id, user_id)
    async with _lock(key):
        if notice_type == "group_decrease":
            await database(leave_group, key, int(event.time))
        elif str(user_id) != str(bot.self_id):
            item_id = await database(prepare_join, key, int(event.time))
            if item_id is not None:
                await _challenge(bot, key, item_id, welcome=True)


async def handle_message(bot: VerificationBot, event: Any) -> bool:
    if str(event.user_id) == str(bot.self_id):
        return False
    key = (str(bot.self_id), event.group_id, event.user_id)
    async with _lock(key):
        result = await database(
            consume_message, key, event.message_id, int(event.time), event.get_plaintext()
        )
        action = result["action"]
        if action == "ignore":
            return False
        if action == "refresh":
            await _challenge(bot, key, result["id"])
        elif action == "passed":
            await _send(bot, key, "验证通过，欢迎你！")
        elif action in {"mute", "kick"}:
            data = {"group_id": key[1], "user_id": key[2]}
            if action == "mute":
                data["duration"] = result["seconds"]
            else:
                data["reject_add_request"] = False
            error = await _api(
                bot, "set_group_ban" if action == "mute" else "set_group_kick", **data
            )
            await database(record_action, result["id"], action, error)
            if error:
                text = "验证码错误；自动处理失败，请管理员检查机器人禁言和踢人权限。"
                if action == "mute":
                    text += f"请等待 {result['seconds']} 秒后重试。"
            elif action == "kick":
                text = "验证码累计答错 4 次，已移出本群。"
            else:
                text = (
                    f"验证码错误（第 {result['wrong_attempts']}/4 次），"
                    f"已禁言 {result['seconds']} 秒，请解禁后重试。"
                )
            await _send(bot, key, text)
        return True
