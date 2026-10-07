import asyncio
import time
from dataclasses import dataclass
from functools import partial
from typing import Callable

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, TypeAdapter, ValidationError, create_model
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.models import Admin, AuditLog
from app.schemas.admin import TencentCloudTmsConfigIn, TencentCloudTmsConfigOut
from app.schemas.resources import LIST_MODELS, DETAIL_MODELS
from app.schemas.rpc import (
    AuthInput,
    BreakdownOut,
    BrowseInput,
    FileUrlInput,
    FileUrlOut,
    FileEntryOut,
    GroupActivityOut,
    GroupOptionOut,
    DashboardSummaryOut,
    IdInput,
    Input,
    JobInput,
    JobOut,
    JobRef,
    MemberActivityOut,
    MoveInput,
    PageInput,
    PageResult,
    OkOut,
    Request,
    RequestIdInput,
    TopicsInput,
    TrendsOut,
    WriteInput,
)
from app.services import onebot
from app.services.admin import dashboard, files, jobs, resources
from app.services.admin.runtime import database, hub, valid_topic
from app.services.tencentcloud_tms_config import get_tms_config, tms_config_out, update_tms_config

router = APIRouter()


@dataclass
class Method:
    schema: type[BaseModel]
    handler: Callable
    write: bool = False
    output: object = dict

    def __post_init__(self):
        self.adapter = TypeAdapter(self.output)


def authenticate(session: Session, token: str) -> tuple[int, float]:
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(401, "登录已失效") from exc
    admin = session.exec(select(Admin).where(Admin.username == payload.get("sub"))).first()
    if admin is None:
        raise HTTPException(401, "管理员不存在")
    return admin.id, float(payload["exp"])


async def resource_list(resource, params, *_):
    return await database(resources.list_resource, resource, params)


async def resource_detail(resource, params, *_):
    return await database(resources.get_resource, resource, params.id)


async def resource_write(resource, action, params, admin_id, *_):
    return await database(resources.write_resource, resource, action, params, admin_id)


async def resource_delete(resource, params, admin_id, *_):
    return await database(resources.delete_resource, resource, params.id, admin_id)


def cloud_read(session):
    return tms_config_out(get_tms_config(session))


def cloud_write(session, params, admin_id):
    config = update_tms_config(session, params)
    session.add(
        AuditLog(
            admin_id=admin_id,
            action="cloud.update",
            target=str(config.id),
            detail={"secret_key_configured": bool(config.secret_key)},
        )
    )
    session.commit()
    return tms_config_out(config)


def build_methods() -> dict[str, Method]:
    methods = {}
    for resource, (_, create_schema, _) in resources.RESOURCES.items():
        methods[f"{resource}.list"] = Method(
            PageInput, partial(resource_list, resource), output=PageResult[LIST_MODELS[resource]]
        )
        methods[f"{resource}.get"] = Method(
            IdInput, partial(resource_detail, resource), output=DETAIL_MODELS[resource]
        )
        if create_schema:
            for action in ("create", "update"):
                methods[f"{resource}.{action}"] = Method(
                    WriteInput,
                    partial(resource_write, resource, action),
                    True,
                    DETAIL_MODELS[resource],
                )
            methods[f"{resource}.delete"] = Method(
                IdInput, partial(resource_delete, resource), True, OkOut
            )

    async def options(params, *_):
        result = await database(resources.list_resource, "groups", params)
        result.items = [
            {key: row[key] for key in ("id", "group_id", "name", "enabled")} for row in result.items
        ]
        return result

    methods["groups.options"] = Method(PageInput, options, output=PageResult[GroupOptionOut])

    async def move(params, admin_id, *_):
        return await database(resources.move_group, params, admin_id)

    methods["groups.move"] = Method(MoveInput, move, True, OkOut)
    GroupRow = LIST_MODELS["groups"]
    LeaveRow = LIST_MODELS["leaves"]
    AuditRow = LIST_MODELS["audits"]
    outputs = {
        "summary": DashboardSummaryOut,
        "trends": TrendsOut,
        "breakdown": BreakdownOut,
        "rankings": create_model(
            "RankingsOut",
            top_groups=(list[GroupRow], ...),
            active_groups=(list[GroupActivityOut], ...),
            active_members=(list[MemberActivityOut], ...),
        ),
        "recent": create_model(
            "RecentOut",
            leaves=(list[LeaveRow], ...),
            audits=(list[AuditRow], ...),
        ),
    }
    for section in ("summary", "trends", "breakdown", "rankings", "recent"):

        async def query(params, *_, section=section):
            return await database(dashboard.dashboard_section, section)

        methods[f"dashboard.{section}"] = Method(Input, query, output=outputs[section])
    for kind in jobs.KINDS:

        async def submit(params, admin_id, request_id, kind=kind):
            return await jobs.submit(kind, params, admin_id, request_id)

        methods[kind] = Method(JobInput, submit, True, JobRef)

    async def browse(params, *_):
        return await files.browse(params)

    methods["files.browse"] = Method(BrowseInput, browse, output=PageResult[FileEntryOut])

    async def url(params, *_):
        return await onebot.get_group_file_url(params.group_id, params.file_id, params.busid)

    methods["files.url"] = Method(FileUrlInput, url, output=FileUrlOut)

    async def job_get(params, *_):
        return await database(jobs.job_out, params.id)

    methods["jobs.get"] = Method(IdInput, job_get, output=JobOut)

    async def actions(params, *_):
        return await database(jobs.job_actions, params.job_id, params)

    methods["jobs.actions"] = Method(PageInput, actions, output=PageResult[LIST_MODELS["actions"]])

    async def find(params, admin_id, *_):
        return await database(jobs.find_request, admin_id, params.request_id)

    methods["jobs.findByRequestId"] = Method(RequestIdInput, find, output=JobRef | None)

    async def config_read(params, *_):
        return await database(cloud_read)

    methods["cloud.get"] = Method(Input, config_read, output=TencentCloudTmsConfigOut)

    async def config_write(params, admin_id, *_):
        return await database(cloud_write, params, admin_id)

    methods["cloud.update"] = Method(
        TencentCloudTmsConfigIn, config_write, True, TencentCloudTmsConfigOut
    )
    return methods


METHODS = build_methods()


def error_payload(exc: Exception) -> dict:
    if isinstance(exc, ValidationError):
        return {
            "code": "VALIDATION_ERROR",
            "message": "请求参数不正确",
            "details": exc.errors(include_context=False),
        }
    if isinstance(exc, IntegrityError):
        return {"code": "CONFLICT", "message": "记录已存在或正在被修改"}
    if isinstance(exc, HTTPException):
        return {
            "code": {
                401: "AUTH_REQUIRED",
                403: "FORBIDDEN",
                404: "NOT_FOUND",
                409: "CONFLICT",
                422: "VALIDATION_ERROR",
            }.get(exc.status_code, "REQUEST_ERROR"),
            "message": str(exc.detail),
        }
    if isinstance(exc, RuntimeError):
        return {"code": "BOT_UNAVAILABLE", "message": str(exc)}
    from nonebot import logger

    logger.opt(exception=exc).error("管理 WS 请求失败")
    return {"code": "INTERNAL_ERROR", "message": "操作失败，请查看服务端日志"}


@router.websocket("/api/admin/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    settings = get_settings()
    origin = ws.headers.get("origin")
    own_origin = f"{'https' if ws.url.scheme == 'wss' else 'http'}://{ws.headers.get('host')}"
    if not origin or (
        "*" not in settings.cors_origin_list
        and origin not in settings.cors_origin_list
        and origin != own_origin
    ):
        await ws.close(code=1008)
        return
    await ws.accept()
    hub.start()
    request_id = ""
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=5)
        if len(raw) > 262144:
            raise HTTPException(422, "消息过大")
        request = Request.model_validate_json(raw)
        request_id = request.id
        if request.method != "auth.authenticate":
            raise HTTPException(401, "请先认证")
        credentials = AuthInput.model_validate(request.params)
        admin_id, expires = await database(authenticate, credentials.token)
        await ws.send_json(
            {
                "v": 1,
                "type": "response",
                "id": request.id,
                "result": {"admin_id": admin_id, "expires_at": expires},
            }
        )
    except Exception as exc:
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            exc = HTTPException(401, "认证超时")
        try:
            await ws.send_json(
                {"v": 1, "type": "response", "id": request_id, "error": error_payload(exc)}
            )
            await ws.close(code=4001)
        except Exception:
            pass
        return
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    subscriptions: set[str] = set()
    hub.listeners[queue] = subscriptions
    pending: set[asyncio.Task] = set()
    in_flight: set[str] = set()
    write_lock = asyncio.Lock()

    async def writer():
        while True:
            message = await queue.get()
            if "close" in message:
                await ws.close(code=message["close"])
                return
            await ws.send_json(message)

    async def expiry():
        await asyncio.sleep(max(0, expires - time.time()))
        await ws.close(code=4001)

    async def handle(request):
        response = {"v": 1, "type": "response", "id": request.id}
        try:
            if time.time() >= expires:
                raise HTTPException(401, "登录已失效")
            if request.method in {"subscribe", "unsubscribe"}:
                params = TopicsInput.model_validate(request.params)
                if any(not valid_topic(topic) for topic in params.topics):
                    raise HTTPException(422, "订阅主题不存在")
                if request.method == "subscribe":
                    if len(subscriptions | set(params.topics)) > 64:
                        raise HTTPException(422, "订阅数量超限")
                    subscriptions.update(params.topics)
                else:
                    subscriptions.difference_update(params.topics)
                result = {"ok": True}
            elif request.method == "ping":
                result = {"pong": True}
            else:
                method = METHODS.get(request.method)
                if method is None:
                    raise HTTPException(404, "方法不存在")
                params = method.schema.model_validate(request.params)
                if method.write:
                    async with write_lock:
                        result = await method.handler(params, admin_id, request.id)
                else:
                    result = await method.handler(params, admin_id, request.id)
                result = method.adapter.validate_python(result)
            response["result"] = jsonable_encoder(result)
        except Exception as exc:
            response["error"] = error_payload(exc)
        finally:
            in_flight.discard(request.id)
        if queue.full():
            await ws.close(code=1013)
        else:
            queue.put_nowait(response)

    sender = asyncio.create_task(writer())
    expiration = asyncio.create_task(expiry())
    try:
        while True:
            raw = await ws.receive_text()
            request_id = ""
            try:
                if len(raw) > 262144:
                    raise HTTPException(422, "消息过大")
                request = Request.model_validate_json(raw)
                request_id = request.id
                if len(pending) >= 8 or request.id in in_flight:
                    raise HTTPException(409, "请求正在处理中或并发数量超限")
                in_flight.add(request.id)
                task = asyncio.create_task(handle(request))
                pending.add(task)
                task.add_done_callback(pending.discard)
            except (ValidationError, HTTPException) as exc:
                await queue.put(
                    {"v": 1, "type": "response", "id": request_id, "error": error_payload(exc)}
                )
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.listeners.pop(queue, None)
        sender.cancel()
        expiration.cancel()
        for task in pending:
            task.cancel()
        await asyncio.gather(sender, expiration, *pending, return_exceptions=True)
