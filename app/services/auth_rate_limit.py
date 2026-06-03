from __future__ import annotations

import math
import time
from dataclasses import dataclass

from fastapi import Request

from app.core.config import Settings, get_settings


@dataclass
class LoginFailureBucket:
    count: int
    first_failure_at: float
    locked_until: float = 0.0


_failures: dict[str, LoginFailureBucket] = {}


def get_client_ip(request: Request, trust_proxy_headers: bool = False) -> str:
    if trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip() or "unknown"
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
    return request.client.host if request.client else "unknown"


def login_rate_limit_keys(
    username: str,
    request: Request,
    settings: Settings | None = None,
) -> list[str]:
    settings = settings or get_settings()
    normalized_username = username.strip().lower() or "unknown"
    client_ip = get_client_ip(request, settings.login_rate_limit_trust_proxy_headers)
    return [f"user:{normalized_username}", f"ip:{client_ip}"]


def assert_login_allowed(
    keys: list[str],
    settings: Settings | None = None,
    now: float | None = None,
) -> None:
    settings = settings or get_settings()
    if settings.login_rate_limit_max_failures <= 0:
        return
    now = now if now is not None else time.time()
    _prune_expired(now, settings)
    for key in keys:
        bucket = _failures.get(key)
        if bucket and bucket.locked_until > now:
            wait_seconds = math.ceil(bucket.locked_until - now)
            raise LoginRateLimitExceeded(max(1, wait_seconds))


def record_login_failure(
    keys: list[str],
    settings: Settings | None = None,
    now: float | None = None,
) -> None:
    settings = settings or get_settings()
    now = now if now is not None else time.time()
    if settings.login_rate_limit_max_failures <= 0:
        return
    _prune_expired(now, settings)
    for key in keys:
        bucket = _failures.get(key)
        if not bucket or now - bucket.first_failure_at > settings.login_rate_limit_window_seconds:
            bucket = LoginFailureBucket(count=0, first_failure_at=now)
            _failures[key] = bucket
        bucket.count += 1
        if bucket.count >= settings.login_rate_limit_max_failures:
            bucket.locked_until = now + settings.login_rate_limit_lock_seconds


def clear_login_failures(keys: list[str]) -> None:
    for key in keys:
        _failures.pop(key, None)


def reset_login_failures() -> None:
    _failures.clear()


def _prune_expired(now: float, settings: Settings) -> None:
    for key, bucket in list(_failures.items()):
        if bucket.locked_until > now:
            continue
        if now - bucket.first_failure_at > settings.login_rate_limit_window_seconds:
            _failures.pop(key, None)


class LoginRateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
