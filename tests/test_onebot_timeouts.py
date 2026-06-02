import pytest

from app.core.config import Settings
from app.services import onebot


@pytest.mark.asyncio
async def test_group_member_list_uses_configured_long_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        onebot,
        "get_settings",
        lambda: Settings(group_member_sync_timeout_seconds=300),
    )

    async def fake_call_onebot(api: str, **data: object) -> list[dict[str, object]]:
        calls.append((api, data))
        return []

    monkeypatch.setattr(onebot, "call_onebot", fake_call_onebot)
    await onebot.get_group_member_list(1001)

    assert calls == [
        (
            "get_group_member_list",
            {"group_id": 1001, "_timeout": 300.0},
        )
    ]
