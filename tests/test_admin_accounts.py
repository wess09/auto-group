import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from starlette.websockets import WebSocketDisconnect

from app.api import auth, admin as upload_api, websocket
from app.core.database import get_session
from app.core.config import Settings
from app.core.security import create_access_token, hash_password
from app.models import Admin, AuditLog
from app.services import admin_accounts, audit
from app.services.admin import runtime
from app.services.auth_rate_limit import reset_login_failures


@pytest.fixture
def system(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'admins.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(runtime, "engine", engine)
    settings = Settings(
        _env_file=None, upload_dir=str(tmp_path / "uploads"), login_rate_limit_max_failures=100
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(upload_api, "get_settings", lambda: settings)
    runtime.hub.pending.clear()
    runtime.hub.versions.clear()
    reset_login_failures()
    with Session(engine) as session:
        session.add_all(
            [
                Admin(
                    username="owner",
                    display_name="群主",
                    password_hash=hash_password("owner-password"),
                    role="superadmin",
                ),
                Admin(
                    username="worker",
                    display_name="值班管理员",
                    password_hash=hash_password("worker-password"),
                ),
            ]
        )
        session.commit()
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(upload_api.router)
    app.include_router(websocket.router)

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def login(client, username="owner", password=None):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password or username + "-password"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def headers(token):
    return {"authorization": "Bearer " + token}


def connect(client):
    return client.websocket_connect(
        "/api/admin/ws", headers={"origin": "http://testserver", "user-agent": "audit-test-agent"}
    )


def rpc(ws, method, params=None, rid="request"):
    ws.send_json({"v": 1, "id": rid, "method": method, "params": params or {}})
    while True:
        result = ws.receive_json()
        if result.get("id") == rid:
            return result


def authenticate(ws, token):
    result = rpc(ws, "auth.authenticate", {"token": token})
    assert "result" in result, result
    return result["result"]["admin_id"]


def test_each_admin_has_independent_login_and_no_secret_profile(system):
    client, _ = system
    profiles = []
    for name in ("owner", "worker"):
        result = client.get("/api/auth/me", headers=headers(login(client, name)))
        assert result.status_code == 200
        profile = result.json()
        assert not {"password_hash", "totp_secret", "token_version"} & profile.keys()
        profiles.append(profile)
    assert profiles[0]["id"] != profiles[1]["id"]
    assert [profile["role"] for profile in profiles] == ["superadmin", "admin"]


def test_superadmin_can_create_and_edit_without_exposing_passwords(system):
    client, _ = system
    token = login(client)
    with connect(client) as ws:
        authenticate(ws, token)
        created = rpc(
            ws,
            "admins.create",
            {"username": "new-admin", "password": "new-password", "display_name": "新管理员"},
        )["result"]
        assert created["role"] == "admin" and created["enabled"]
        assert "password" not in json.dumps(created)
        row = rpc(
            ws,
            "admins.update",
            {"id": created["id"], "display_name": "编辑后", "role": "superadmin"},
        )["result"]
        assert row["display_name"] == "编辑后" and row["role"] == "superadmin"
        listed = rpc(ws, "admins.list")["result"]
        assert listed["total"] == 3
        assert "password_hash" not in json.dumps(listed) and "totp_secret" not in json.dumps(listed)
        assert (
            rpc(ws, "admins.create", {"username": "new-admin", "password": "new-password"})[
                "error"
            ]["code"]
            == "CONFLICT"
        )
        assert rpc(ws, "admins.delete", {"id": created["id"]})["error"]["code"] == "NOT_FOUND"
    assert login(client, "new-admin", "new-password")


@pytest.mark.parametrize(
    "method,params",
    [
        ("admins.list", {}),
        ("admins.get", {"id": 1}),
        (
            "admins.create",
            {"username": "attack", "password": "attack-password", "role": "superadmin"},
        ),
        ("admins.update", {"id": 2, "role": "superadmin"}),
        ("admins.reset-password", {"id": 1, "password": "attack-password"}),
        ("admins.reset-2fa", {"id": 1}),
        ("subscribe", {"topics": ["admins"]}),
    ],
)
def test_normal_admin_cannot_manage_accounts(system, method, params):
    client, engine = system
    with connect(client) as ws:
        authenticate(ws, login(client, "worker"))
        assert rpc(ws, method, params)["error"]["code"] == "FORBIDDEN"
    with Session(engine) as session:
        assert session.get(Admin, 2).role == "admin"
        if method != "subscribe":
            entry = session.exec(select(AuditLog).where(AuditLog.action == f"rpc.{method}")).one()
            assert entry.actor_username == "worker" and entry.status == "failed"


def test_normal_admin_business_changes_have_identity_source_and_before_after(system):
    client, engine = system
    with connect(client) as ws:
        authenticate(ws, login(client, "worker"))
        row = rpc(
            ws, "groups.create", {"data": {"group_id": 1001, "name": "原名称"}}, "create-group"
        )["result"]
        rpc(ws, "groups.update", {"id": row["id"], "data": {"name": "新名称"}}, "edit-group")
    with Session(engine) as session:
        entry = session.exec(select(AuditLog).where(AuditLog.action == "groups.update")).one()
        assert (entry.admin_id, entry.actor_username, entry.actor_name) == (
            2,
            "worker",
            "值班管理员",
        )
        assert entry.client_ip == "testclient" and entry.user_agent == "audit-test-agent"
        assert entry.request_id == "edit-group" and entry.transport == "ws"
        assert (
            entry.detail["before"]["name"] == "原名称" and entry.detail["after"]["name"] == "新名称"
        )


@pytest.mark.parametrize(
    "mutation,params",
    [
        ("admins.update", {"id": 2, "enabled": False}),
        ("admins.update", {"id": 2, "role": "superadmin"}),
        ("admins.reset-password", {"id": 2, "password": "changed-password"}),
        ("admins.reset-2fa", {"id": 2}),
    ],
)
def test_account_changes_close_existing_ws_and_invalidate_http_tokens(system, mutation, params):
    client, _ = system
    owner, worker = login(client), login(client, "worker")
    with connect(client) as live:
        authenticate(live, worker)
        with connect(client) as control:
            authenticate(control, owner)
            assert "result" in rpc(control, mutation, params)
        with pytest.raises(WebSocketDisconnect) as exc:
            live.receive_json()
        assert exc.value.code == 4001
    assert client.get("/api/auth/me", headers=headers(worker)).status_code == 401
    assert (
        client.get("/api/auth/me", headers=headers(create_access_token("worker"))).status_code
        == 401
    )


def test_disabled_account_cannot_login_and_self_lockout_is_blocked(system):
    client, _ = system
    with connect(client) as ws:
        authenticate(ws, login(client))
        for data in ({"enabled": False}, {"role": "admin"}):
            assert rpc(ws, "admins.update", {"id": 1, **data})["error"]["code"] == "CONFLICT"
        rpc(ws, "admins.update", {"id": 2, "enabled": False})
    assert (
        client.post(
            "/api/auth/login", json={"username": "worker", "password": "worker-password"}
        ).status_code
        == 401
    )


def test_password_change_and_logout_revoke_login_with_audited_outcomes(system):
    client, engine = system
    token = login(client, "worker")
    wrong = client.post(
        "/api/auth/password",
        headers=headers(token),
        json={"current_password": "wrong-secret", "new_password": "changed-password"},
    )
    assert wrong.status_code == 400
    result = client.post(
        "/api/auth/password",
        headers=headers(token),
        json={"current_password": "worker-password", "new_password": "changed-password"},
    )
    assert result.status_code == 200
    assert client.get("/api/auth/me", headers=headers(token)).status_code == 401
    new_token = login(client, "worker", "changed-password")
    assert client.post("/api/auth/logout", headers=headers(new_token)).status_code == 200
    assert client.get("/api/auth/me", headers=headers(new_token)).status_code == 401
    with Session(engine) as session:
        changes = session.exec(
            select(AuditLog).where(AuditLog.action == "auth.change-password")
        ).all()
        assert [entry.status for entry in changes] == ["failed", "success"]
        logs = "\n".join(entry.model_dump_json() for entry in session.exec(select(AuditLog)).all())
        for secret in ("wrong-secret", "worker-password", "changed-password", token, new_token):
            assert secret not in logs


def test_auth_validation_failures_uploads_and_totp_setup_are_audited(system):
    client, engine = system
    token = login(client, "worker")
    assert client.post("/api/auth/login", json={"username": "worker"}).status_code == 422
    assert (
        client.post(
            "/api/auth/login", json={"username": "unknown", "password": "secret-attempt"}
        ).status_code
        == 401
    )
    first = client.post("/api/auth/2fa/setup", headers=headers(token)).json()
    owner = login(client)
    second = client.post("/api/auth/2fa/setup", headers=headers(owner)).json()
    assert first["secret"] != second["secret"]
    assert (
        client.post(
            "/api/auth/2fa/enable", headers=headers(token), json={"code": "bad"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/admin/uploads", headers=headers(token), files={"file": ("test.txt", b"test")}
        ).status_code
        == 200
    )
    with Session(engine) as session:
        logs = session.exec(select(AuditLog)).all()
        exported = "\n".join(entry.model_dump_json() for entry in logs)
        assert first["secret"] not in exported and second["secret"] not in exported
        assert "secret-attempt" not in exported
        uploaded = next(row for row in logs if row.action == "files.upload")
        request_log = next(row for row in logs if row.action == "http.admin.uploads")
        assert uploaded.request_id == request_log.request_id and uploaded.request_id
        success = next(
            row for row in logs if row.action == "http.auth.login" and row.status == "success"
        )
        assert success.admin_id is not None
        assert any(
            row.action == "http.auth.login" and row.detail["status_code"] == 422 for row in logs
        )
        assert any(
            row.action == "auth.login"
            and row.status == "failed"
            and row.actor_username == "unknown"
            for row in logs
        )
        assert any(
            row.action == "files.upload"
            and row.actor_username == "worker"
            and row.detail["size"] == 4
            for row in logs
        )


def test_audit_read_is_filterable_and_does_not_trigger_audit_refresh_loop(system):
    client, _ = system
    token = login(client, "worker")
    with connect(client) as ws:
        authenticate(ws, token)
        before = runtime.hub.versions.get("audits", 0)
        result = rpc(ws, "audits.list", {"admin_id": 2, "q": "worker"})["result"]
        assert result["total"] > 0
        assert all(row["actor_username"] == "worker" for row in result["items"])
        assert runtime.hub.versions.get("audits", 0) == before
        assert (
            rpc(ws, "audits.delete", {"id": result["items"][0]["id"]})["error"]["code"]
            == "NOT_FOUND"
        )


def test_nested_credentials_are_redacted_and_failed_changes_do_not_revoke(system):
    _, engine = system
    assert audit.redact(
        {
            "channels": [
                {
                    "api_key": "key",
                    "proxy_url": "http://user:pass@host",
                    "headers": {"Authorization": "Bearer secret"},
                }
            ]
        }
    ) == {
        "channels": [
            {
                "api_key": "[已隐藏]",
                "proxy_url": "[已隐藏]",
                "headers": {"Authorization": "[已隐藏]"},
            }
        ]
    }
    with Session(engine) as session:
        worker = session.get(Admin, 2)
        admin_accounts.invalidate(session, worker)
        session.rollback()
    with Session(engine) as session:
        assert session.get(Admin, 2).token_version == 0


def test_current_display_name_is_snapshotted_without_rewriting_previous_logs(system):
    client, engine = system
    with connect(client) as ws:
        authenticate(ws, login(client))
        rpc(ws, "admins.update", {"id": 1, "display_name": "新群主"})
        rpc(ws, "groups.create", {"data": {"group_id": 456}})
    with Session(engine) as session:
        renamed = session.exec(select(AuditLog).where(AuditLog.action == "admins.update")).one()
        created = session.exec(select(AuditLog).where(AuditLog.action == "groups.create")).one()
        assert renamed.actor_name == "群主" and created.actor_name == "新群主"


def test_revocations_increment_even_when_a_second_session_loaded_an_old_version(system):
    _, engine = system
    with Session(engine) as first, Session(engine) as second:
        a, b = first.get(Admin, 2), second.get(Admin, 2)
        assert a.token_version == b.token_version == 0
        admin_accounts.invalidate(first, a)
        first.commit()
        admin_accounts.invalidate(second, b)
        second.commit()
    with Session(engine) as session:
        assert session.get(Admin, 2).token_version == 2


def test_totp_changes_are_per_account_and_revoke_old_logins(system, monkeypatch):
    client, engine = system
    owner, worker = login(client), login(client, "worker")
    secret = client.post("/api/auth/2fa/setup", headers=headers(worker)).json()["secret"]
    monkeypatch.setattr(
        auth, "verify_totp", lambda stored, code: stored == secret and code == "123456"
    )
    enabled = client.post("/api/auth/2fa/enable", headers=headers(worker), json={"code": "123456"})
    assert enabled.status_code == 200
    assert client.get("/api/auth/me", headers=headers(worker)).status_code == 401
    assert client.get("/api/auth/me", headers=headers(owner)).status_code == 200
    assert (
        client.post(
            "/api/auth/login", json={"username": "worker", "password": "worker-password"}
        ).status_code
        == 401
    )
    result = client.post(
        "/api/auth/login",
        json={"username": "worker", "password": "worker-password", "totp_code": "123456"},
    )
    assert result.status_code == 200
    token = result.json()["access_token"]
    assert (
        client.post(
            "/api/auth/2fa/disable", headers=headers(token), json={"code": "123456"}
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me", headers=headers(token)).status_code == 401
    assert login(client, "worker")
    with Session(engine) as session:
        exported = "\n".join(row.model_dump_json() for row in session.exec(select(AuditLog)).all())
        assert secret not in exported and "123456" not in exported
