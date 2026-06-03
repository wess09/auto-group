from dataclasses import dataclass

import pytest

from app.core.config import Settings
from app.services.auth_rate_limit import (
    LoginRateLimitExceeded,
    assert_login_allowed,
    clear_login_failures,
    get_client_ip,
    record_login_failure,
    reset_login_failures,
)


@pytest.fixture(autouse=True)
def clear_rate_limit_state() -> None:
    reset_login_failures()


def test_login_rate_limit_locks_after_configured_failures() -> None:
    settings = Settings(
        login_rate_limit_max_failures=2,
        login_rate_limit_window_seconds=60,
        login_rate_limit_lock_seconds=30,
    )
    keys = ["user:admin", "ip:127.0.0.1"]

    record_login_failure(keys, settings, now=100)
    assert_login_allowed(keys, settings, now=101)
    record_login_failure(keys, settings, now=102)

    with pytest.raises(LoginRateLimitExceeded) as exc_info:
        assert_login_allowed(keys, settings, now=103)

    assert exc_info.value.retry_after_seconds == 29


def test_login_rate_limit_expires_after_lock() -> None:
    settings = Settings(
        login_rate_limit_max_failures=1,
        login_rate_limit_window_seconds=60,
        login_rate_limit_lock_seconds=30,
    )
    keys = ["user:admin"]

    record_login_failure(keys, settings, now=100)

    assert_login_allowed(keys, settings, now=131)


def test_clear_login_failures_allows_retry() -> None:
    settings = Settings(
        login_rate_limit_max_failures=1,
        login_rate_limit_window_seconds=60,
        login_rate_limit_lock_seconds=30,
    )
    keys = ["user:admin"]

    record_login_failure(keys, settings, now=100)
    clear_login_failures(keys)

    assert_login_allowed(keys, settings, now=101)


def test_get_client_ip_ignores_forwarded_header_by_default() -> None:
    request = FakeRequest(
        headers={"x-forwarded-for": "203.0.113.10"},
        client=FakeClient(host="127.0.0.1"),
    )

    assert get_client_ip(request) == "127.0.0.1"


def test_get_client_ip_uses_forwarded_header_when_trusted() -> None:
    request = FakeRequest(
        headers={"x-forwarded-for": "203.0.113.10, 198.51.100.20"},
        client=FakeClient(host="127.0.0.1"),
    )

    assert get_client_ip(request, trust_proxy_headers=True) == "203.0.113.10"


@dataclass
class FakeClient:
    host: str


@dataclass
class FakeRequest:
    headers: dict[str, str]
    client: FakeClient
