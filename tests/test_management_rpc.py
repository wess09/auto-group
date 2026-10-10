import asyncio
import time
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, create_engine, select
from starlette.websockets import WebSocketDisconnect

from app.api import websocket
from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.models import (
    Admin,
    AuditLog,
    DedupeAction,
    DedupeJob,
    DedupeWhitelist,
    GroupMember,
    ManagedGroup,
)
from app.models.entities import AdminJob, AdminJobItem
from app.schemas.rpc import Input, JobInput, PageInput, Selection, WriteInput
from app.services.admin import dashboard, files, jobs, resources, runtime


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'rpc.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(runtime, "engine", engine)
    runtime.hub.pending.clear()
    runtime.hub.versions.clear()
    dashboard.cache.clear()
    files.cache.clear()
    with Session(engine) as session:
        session.add(Admin(username="admin", password_hash="unused"))
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(websocket.router)
    with TestClient(app) as client:
        yield client


def authenticate(ws, token=None):
    ws.send_json(
        {
            "v": 1,
            "id": "auth",
            "method": "auth.authenticate",
            "params": {"token": token or create_access_token("admin")},
        }
    )
    result = ws.receive_json()
    assert result["id"] == "auth" and "result" in result


def call(ws, method, params=None, request_id="query"):
    ws.send_json({"v": 1, "id": request_id, "method": method, "params": params or {}})
    while True:
        response = ws.receive_json()
        if response.get("id") == request_id:
            return response


def test_authentication_is_required(client):
    with client.websocket_connect("/api/admin/ws", headers={"origin": "http://testserver"}) as ws:
        result = call(ws, "groups.list")
        assert result["error"]["code"] == "AUTH_REQUIRED"
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4001


def test_recall_admin_crud_and_permissions(client, db):
    from app.services.bulk_recall import is_admin

    with client.websocket_connect("/api/admin/ws", headers={"origin": "http://testserver"}) as ws:
        authenticate(ws)
        for user_id in (0, -1, 1.5, True, "123"):
            result = call(ws, "recall-admins.create", {"data": {"user_id": user_id}})
            assert result["error"]["code"] == "VALIDATION_ERROR"
        row = call(ws, "recall-admins.create", {"data": {"user_id": 123, "note": "test"}})["result"]
        duplicate = call(ws, "recall-admins.create", {"data": {"user_id": 123}})
        assert duplicate["error"]["code"] == "CONFLICT"
        assert call(ws, "recall-admins.list", {"q": "123"})["result"]["total"] == 1
        assert call(ws, "recall-admins.get", {"id": row["id"]})["result"]["note"] == "test"
        with Session(db) as session:
            assert is_admin(session, 123)
        call(ws, "recall-admins.update", {"id": row["id"], "data": {"enabled": False}})
        with Session(db) as session:
            assert not is_admin(session, 123)
        call(ws, "recall-admins.delete", {"id": row["id"]})
        assert call(ws, "recall-admins.list")["result"]["total"] == 0


def test_invalid_token_is_rejected(client):
    with client.websocket_connect("/api/admin/ws", headers={"origin": "http://testserver"}) as ws:
        result = call(ws, "auth.authenticate", {"token": "invalid"})
        assert result["error"]["code"] == "AUTH_REQUIRED"


def test_authentication_timeout(client):
    with client.websocket_connect("/api/admin/ws", headers={"origin": "http://testserver"}) as ws:
        result = ws.receive_json()
        assert result["error"]["code"] == "AUTH_REQUIRED"
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4001


def test_origin_is_checked(client, monkeypatch):
    monkeypatch.setattr(
        websocket, "get_settings", lambda: Settings(cors_origins="https://allowed.example")
    )
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/admin/ws", headers={"origin": "https://other.example"}):
            pass


def test_expired_token_closes_existing_connection(client):
    settings = get_settings()
    token = jwt.encode(
        {"sub": "admin", "exp": int(time.time()) + 2},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with client.websocket_connect("/api/admin/ws", headers={"origin": "http://testserver"}) as ws:
        authenticate(ws, token)
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4001


def test_unknown_method_and_validation_errors_keep_request_id(client):
    with client.websocket_connect("/api/admin/ws", headers={"origin": "http://testserver"}) as ws:
        authenticate(ws)
        assert call(ws, "missing", request_id="unknown")["error"]["code"] == "NOT_FOUND"
        for params in ({"page_size": 101}, {"page": 0}, {"start_date": "bad"}, {"unexpected": 1}):
            result = call(ws, "groups.list", params, "invalid")
            assert result["id"] == "invalid" and result["error"]["code"] == "VALIDATION_ERROR"


def test_concurrent_responses_are_correlated(client, monkeypatch):
    async def slow(params, *_):
        await asyncio.sleep(0.05)
        return {"slow": True}

    monkeypatch.setitem(websocket.METHODS, "test.slow", websocket.Method(Input, slow))
    with client.websocket_connect("/api/admin/ws", headers={"origin": "http://testserver"}) as ws:
        authenticate(ws)
        for identifier, method in (("slow", "test.slow"), ("fast", "ping")):
            ws.send_json({"v": 1, "id": identifier, "method": method, "params": {}})
        first, second = ws.receive_json(), ws.receive_json()
        assert first["id"] == "fast" and second["id"] == "slow"


def test_subscription_and_unsubscribe(client):
    with client.websocket_connect("/api/admin/ws", headers={"origin": "http://testserver"}) as ws:
        authenticate(ws)
        assert call(ws, "subscribe", {"topics": ["groups"]})["result"]["ok"]
        call(ws, "groups.create", {"data": {"group_id": 42, "name": "new"}}, "write")
        event = ws.receive_json()
        assert event == {"v": 1, "type": "event", "topic": "groups", "payload": {}}
        call(ws, "unsubscribe", {"topics": ["groups"]}, "stop")
        assert not any("groups" in topics for topics in runtime.hub.listeners.values())


def test_reconnect_queries_current_state(client):
    for number in range(2):
        with client.websocket_connect(
            "/api/admin/ws", headers={"origin": "http://testserver"}
        ) as ws:
            authenticate(ws)
            if number == 0:
                call(ws, "groups.create", {"data": {"group_id": 42}}, "write")
            result = call(ws, "groups.list")["result"]
            assert result["total"] == 1 and len(result["items"]) == 1


def test_notifications_only_follow_commits(db):
    version = runtime.hub.versions.get("groups", 0)
    with Session(db) as session:
        session.add(ManagedGroup(group_id=123))
        session.flush()
        session.rollback()
    assert runtime.hub.versions.get("groups", 0) == version
    with Session(db) as session:
        session.add(ManagedGroup(group_id=123))
        session.commit()
    assert runtime.hub.versions["groups"] == version + 1


def test_ten_thousand_logs_and_actions_are_paginated(db):
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with Session(db) as session:
        session.add_all(
            [
                AuditLog(action=f"event-{i}", created_at=created, detail={"large": "x" * 1000})
                for i in range(10000)
            ]
        )
        session.add_all(
            [
                DedupeAction(job_id=1, user_id=i, keep_group_id=10, kick_group_id=20)
                for i in range(10000)
            ]
        )
        session.commit()
        first = resources.list_resource(session, "audits", PageInput())
        second = resources.list_resource(session, "audits", PageInput(page=2))
        assert first.total == second.total == 10000
        assert len(first.items) == len(second.items) == 25
        assert set(row["id"] for row in first.items).isdisjoint(row["id"] for row in second.items)
        assert "detail" not in first.items[0]
        assert resources.get_resource(session, "audits", first.items[0]["id"])["detail"]
        assert resources.list_resource(session, "audits", PageInput(page=1000)).items == []
        actions = resources.list_resource(session, "actions", PageInput(job_id=1, page=400))
        assert actions.total == 10000 and len(actions.items) == 25


def test_search_selection_and_move_across_pages(db):
    with Session(db) as session:
        session.add_all(
            [
                ManagedGroup(group_id=i, priority=100, name=f"team {i}", enabled=i % 2 == 0)
                for i in range(1, 61)
            ]
        )
        session.commit()
        assert resources.list_resource(session, "groups", PageInput(q="team 1")).total == 11
        selected = resources.resolve_selection(
            session, Selection(mode="all_matching", enabled=True, excluded_ids=[2])
        )
        assert len(selected) == 29 and 2 not in selected
        from app.schemas.rpc import MoveInput

        resources.move_group(session, MoveInput(group_id=60, position=1), 1)
        first = resources.list_resource(session, "groups", PageInput())
        assert first.items[0]["group_id"] == 60


def test_job_submission_is_idempotent_and_freezes_targets(db):
    with Session(db) as session:
        session.add_all([ManagedGroup(group_id=10), ManagedGroup(group_id=20)])
        session.commit()
        args = JobInput(selection=Selection(mode="all_matching"), content="hello")
        first, created = jobs.create_job(session, "notices.send", args, 1, "same-request")
        second, duplicate = jobs.create_job(session, "notices.send", args, 1, "same-request")
        assert created and not duplicate and first.id == second.id
        session.add(ManagedGroup(group_id=30))
        session.commit()
        assert session.get(AdminJob, first.id).params["targets"] == [10, 20]


@pytest.mark.asyncio
async def test_partial_failure_and_restart_recovery(db, monkeypatch):
    async def perform(kind, gid, params):
        if gid == 20:
            raise RuntimeError("upstream failure")

    monkeypatch.setattr(jobs, "perform", perform)
    with Session(db) as session:
        session.add_all([ManagedGroup(group_id=10), ManagedGroup(group_id=20)])
        session.commit()
        reference, _ = jobs.create_job(
            session,
            "notices.send",
            JobInput(selection=Selection(mode="all_matching"), content="hello"),
            1,
            "request",
        )
    await jobs.run(reference.id)
    with Session(db) as session:
        job = jobs.job_out(session, reference.id)
        assert job.status == "failed" and job.summary["failed"] == 1
        rows = session.exec(select(AdminJobItem).where(AdminJobItem.job_id == reference.id)).all()
        assert [row.status for row in rows] == ["success", "failed"]
        pending = AdminJob(admin_id=1, request_id="interrupted", kind="notices.send")
        session.add(pending)
        session.commit()
        pending_id = pending.id
        jobs.recover(session)
        assert session.get(AdminJob, pending_id).status == "interrupted"


def test_incomplete_preview_cannot_execute(db):
    with Session(db) as session:
        inner = DedupeJob(status="failed", summary={"failed_groups": [10]})
        session.add(inner)
        session.commit()
        preview = AdminJob(
            admin_id=1,
            request_id="preview",
            kind="dedupe.preview",
            status="failed",
            dedupe_job_id=inner.id,
        )
        session.add(preview)
        session.commit()
        with pytest.raises(Exception, match="完整成功"):
            jobs.create_job(session, "dedupe.execute", JobInput(job_id=preview.id), 1, "execute")


@pytest.mark.asyncio
async def test_directory_cache_is_paged_and_invalidated(monkeypatch):
    calls = []

    async def root(gid):
        calls.append(gid)
        return {"files": [{"file_id": str(i), "file_name": f"file-{i}"} for i in range(1000)]}

    monkeypatch.setattr(files.onebot, "get_group_root_files", root)
    files.cache.clear()
    from app.schemas.rpc import BrowseInput

    first = await files.browse(BrowseInput(group_id=42))
    second = await files.browse(BrowseInput(group_id=42, page=2))
    assert len(first.items) == len(second.items) == 25 and first.total == 1000 and calls == [42]
    files.invalidate(42)
    await files.browse(BrowseInput(group_id=42))
    assert calls == [42, 42]


def test_page_limits_and_unknown_fields():
    with pytest.raises(ValidationError):
        PageInput(page_size=101)
    with pytest.raises(ValidationError):
        PageInput(extra="bad")


def test_image_channels_mask_keys_preserve_them_by_id_and_clear_explicitly(client, db):
    with client.websocket_connect("/api/admin/ws", headers={"origin": "http://testserver"}) as ws:
        authenticate(ws)
        data = {
            "enabled": True,
            "channels": [
                {"id": "a", "name": "主渠道", "model": "vision-a", "api_key": "secret-a"},
                {"id": "b", "name": "备用", "model": "vision-b", "api_key": "secret-b"},
            ],
        }
        saved = call(ws, "image-review.update", data)["result"]
        assert all(channel["api_key_configured"] for channel in saved["channels"])
        assert "secret-a" not in str(saved) and "secret-b" not in str(saved)
        read = call(ws, "image-review.get")["result"]
        assert read == saved
        data["channels"].reverse()
        for channel in data["channels"]:
            channel["api_key"] = ""
        call(ws, "image-review.update", data)
        from app.models import ImageReviewConfig

        with Session(db) as session:
            config = session.exec(select(ImageReviewConfig)).one()
            assert [channel["api_key"] for channel in config.channels] == ["secret-b", "secret-a"]
            audits = session.exec(
                select(AuditLog).where(AuditLog.action == "image-review.update")
            ).all()
            assert "secret-a" not in str([row.detail for row in audits])
        data["channels"][0]["clear_api_key"] = True
        saved = call(ws, "image-review.update", data)["result"]
        assert not saved["channels"][0]["api_key_configured"]
        assert saved["channels"][1]["api_key_configured"]


def test_crud_updates_global_rule_and_audit_in_same_transaction(db):
    with Session(db) as session:
        row = resources.write_resource(
            session,
            "rules",
            "create",
            WriteInput(data={"name": "rule", "patterns": ["yes"], "group_id": 42}),
            1,
        )
        updated = resources.write_resource(
            session, "rules", "update", WriteInput(id=row["id"], data={"group_id": None}), 1
        )
        assert updated["group_id"] is None
        assert resources.list_resource(session, "audits", PageInput()).total == 2
        with pytest.raises(ValidationError):
            resources.write_resource(
                session, "groups", "create", WriteInput(data={"group_id": 99, "unexpected": 1}), 1
            )


@pytest.mark.asyncio
async def test_directory_lock_is_released_on_upstream_failure(monkeypatch):
    async def fail(gid):
        raise RuntimeError("offline")

    monkeypatch.setattr(files.onebot, "get_group_root_files", fail)
    from app.schemas.rpc import BrowseInput

    with pytest.raises(RuntimeError):
        await files.browse(BrowseInput(group_id=123456))
    assert (123456, "") not in files.locks


def test_heavy_statistics_keep_ttl_under_frequent_changes(db, monkeypatch):
    calls = []

    def query(session, section):
        calls.append(section)
        return {"items": []}

    monkeypatch.setattr(dashboard, "query_section", query)
    with Session(db) as session:
        dashboard.dashboard_section(session, "trends")
        runtime.hub.versions["dashboard.trends"] = 100
        dashboard.dashboard_section(session, "trends")
        assert calls == ["trends"]
        dashboard.cache["trends"] = (0, 100, {})
        dashboard.dashboard_section(session, "trends")
        assert calls == ["trends", "trends"]


@pytest.mark.asyncio
async def test_new_dedupe_pipeline_preserves_preview_and_execution_protection(db, monkeypatch):
    kicked = []

    async def members(gid):
        return [
            {"user_id": 42, "role": "member"},
            {"user_id": 43, "role": "member"},
            {"user_id": 44, "role": "admin" if gid == 10 else "member"},
        ]

    async def kick(gid, uid):
        kicked.append((gid, uid))

    monkeypatch.setattr(jobs.onebot, "get_group_member_list", members)
    monkeypatch.setattr(jobs.onebot, "set_group_kick", kick)
    with Session(db) as session:
        session.add_all([ManagedGroup(group_id=10, priority=200), ManagedGroup(group_id=20)])
        session.commit()
        preview, _ = jobs.create_job(session, "dedupe.preview", JobInput(), 1, "preview")
        # A newly enabled group's old snapshot must not enter this already-submitted preview.
        session.add_all(
            [ManagedGroup(group_id=30, priority=1000), GroupMember(group_id=30, user_id=43)]
        )
        session.commit()
    await jobs.run(preview.id)
    with Session(db) as session:
        output = jobs.job_out(session, preview.id)
        assert output.status == "preview" and output.summary["actions"] == 2
        assert (
            output.summary["role_whitelist_skipped"] == 1
            and "skipped_members" not in output.summary
        )
        assert kicked == []
        session.add(DedupeWhitelist(user_id=42))
        session.commit()
        execution, _ = jobs.create_job(
            session, "dedupe.execute", JobInput(job_id=preview.id), 1, "execute"
        )
        assert jobs.job_out(session, execution.id).summary["total"] == 2
        with pytest.raises(Exception, match="预览不完整"):
            jobs.create_job(
                session, "dedupe.execute", JobInput(job_id=preview.id), 1, "second-execute"
            )
    await jobs.run(execution.id)
    with Session(db) as session:
        output = jobs.job_out(session, execution.id)
        assert output.status == "success" and output.summary["skipped"] == 1
        assert kicked == [(20, 43)]
        actions = jobs.job_actions(session, execution.id, PageInput())
        assert sorted(row["status"] for row in actions.items) == ["skipped", "success"]


def test_notice_snapshots_keep_existing_content_readable():
    from app.services.admin.notices import content_text

    assert content_text({"text": "公告原文", "images": []}) == "公告原文"
    assert content_text("{'text': '已有公告', 'images': []}") == "已有公告"
    assert content_text('{"text":"JSON 公告"}') == "JSON 公告"
    assert content_text("纯文本公告") == "纯文本公告"


@pytest.mark.asyncio
async def test_disconnected_submission_still_registers_and_runs_job(db, monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    original_database = jobs.database
    performed = []

    async def delayed_database(fn, *args, **kwargs):
        if fn is jobs.create_job:
            started.set()
            await release.wait()
        return await original_database(fn, *args, **kwargs)

    async def perform(kind, gid, params):
        performed.append(gid)

    monkeypatch.setattr(jobs, "database", delayed_database)
    monkeypatch.setattr(jobs, "perform", perform)
    with Session(db) as session:
        session.add(ManagedGroup(group_id=10))
        session.commit()
    request = asyncio.create_task(
        jobs.submit("notices.send", JobInput(group_id=10, content="hello"), 1, "lost-response")
    )
    await started.wait()
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    registration = list(jobs.tasks)
    release.set()
    await asyncio.gather(*registration)
    await asyncio.gather(*list(jobs.tasks))
    with Session(db) as session:
        receipt = jobs.find_request(session, 1, "lost-response")
        assert receipt is not None
        assert jobs.job_out(session, receipt.id).status == "success"
    assert performed == [10]
