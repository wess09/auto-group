"""HTTP is limited to binary uploads; management methods live in websocket.py."""

import secrets

import aiofiles
from fastapi import APIRouter, File, Request, UploadFile

from app.api.deps import AdminDep
from app.api.audited_route import AuditedRoute
from app.core.config import get_settings
from app.schemas.admin import UploadOut
from app.services import audit
from app.services.admin.runtime import database

router = APIRouter(prefix="/api/admin", tags=["uploads"], route_class=AuditedRoute)


def _status_value(status: object) -> str:
    return str(getattr(status, "value", status))


@router.post("/uploads", response_model=UploadOut)
async def upload_file(admin: AdminDep, request: Request, file: UploadFile = File(...)) -> UploadOut:
    fields = audit.request_context(admin, request)
    folder = get_settings().upload_path
    folder.mkdir(parents=True, exist_ok=True)
    file_name = (file.filename or "file").replace("\\", "/").rsplit("/", 1)[-1]
    path = folder / f"{secrets.token_hex(12)}_{file_name}"
    size = 0
    try:
        async with aiofiles.open(path, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                await output.write(chunk)
    except BaseException as exc:
        path.unlink(missing_ok=True)
        await database(
            audit.record,
            "files.upload",
            status="failed",
            target=file_name,
            details={"error": type(exc).__name__},
            **fields,
        )
        raise
    finally:
        await file.close()
    await database(audit.record, "files.upload", target=file_name, details={"size": size}, **fields)
    return UploadOut(file_name=file_name, file_path=str(path), size=size)
