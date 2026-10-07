"""Isolated browser-test API using the real RPC stack and a fake OneBot transport."""

import asyncio
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
storage = tempfile.TemporaryDirectory(prefix="auto-group-e2e-")
os.environ.update(
    DATABASE_URL=f"sqlite:///{Path(storage.name) / 'test.db'}",
    ADMIN_USERNAME="admin",
    ADMIN_PASSWORD="browser-password",
    UPLOAD_DIR=str(Path(storage.name) / "uploads"),
)

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from sqlmodel import Session  # noqa: E402
from app.api.router import api_router  # noqa: E402
from app.core.database import engine, init_db  # noqa: E402
from app.models import AuditLog, JoinRequest, ManagedGroup  # noqa: E402
from app.services import onebot  # noqa: E402
from app.services.admin import jobs  # noqa: E402
from app.services.admin.runtime import hub  # noqa: E402

init_db()
with Session(engine) as session:
    session.add_all(
        [
            ManagedGroup(
                group_id=1000 + i,
                name=f"测试群 {i}",
                priority=1000 - i,
                join_url="https://example.com/join",
                max_members=1000,
                current_members=100 + i,
            )
            for i in range(1, 61)
        ]
    )
    session.add_all(
        [
            JoinRequest(
                flag=str(i),
                user_id=10000 + i,
                group_id=1001,
                answer_text="示例答案",
                result="approved",
            )
            for i in range(10000)
        ]
    )
    session.add_all(
        [
            AuditLog(action=f"example.{i}", target="1001", detail={"example": "browser fixture"})
            for i in range(10000)
        ]
    )
    session.commit()


async def fake_call(api, **data):
    await asyncio.sleep(0.02)
    if api == "get_group_info":
        return {
            "group_name": f"测试群 {data['group_id'] - 1000}",
            "member_count": 100,
            "max_member_count": 1000,
        }
    if api == "get_group_member_list":
        return [
            {"user_id": 42, "nickname": "重复成员", "role": "member"},
            {"user_id": data["group_id"], "nickname": "普通成员", "role": "member"},
        ]
    if api in {"get_group_root_files", "get_group_files_by_folder"}:
        return {
            "folders": [{"folder_id": "folder-1", "folder_name": "资料"}]
            if api == "get_group_root_files"
            else [],
            "files": [
                {"file_id": str(i), "file_name": f"文件 {i}.txt", "busid": 102, "size": 1024}
                for i in range(120)
            ],
        }
    if api == "get_group_file_url":
        return {"url": "https://example.com/file.txt"}
    if api == "get_group_notices":
        return [{"notice_id": "1", "content": "测试公告内容", "sender_id": 42}]
    if api == "get_essence_msg_list":
        return [{"message_id": 9001, "content": "测试精华内容", "sender_id": 42}]
    if api == "send_group_msg":
        return {"message_id": 9001}
    return {"ok": True}


@asynccontextmanager
async def lifespan(app):
    hub.start()
    yield
    for task in list(jobs.tasks):
        task.cancel()
    await asyncio.gather(*jobs.tasks, return_exceptions=True)


onebot.call_onebot = fake_call
app = FastAPI(lifespan=lifespan)
app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
