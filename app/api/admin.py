"""HTTP is limited to binary uploads; management methods live in websocket.py."""

import secrets

import aiofiles
from fastapi import APIRouter, File, UploadFile

from app.api.deps import AdminDep
from app.core.config import get_settings
from app.schemas.admin import UploadOut

router = APIRouter(prefix="/api/admin", tags=["uploads"])


def _status_value(status: object) -> str:
    return str(getattr(status, "value", status))


@router.post("/uploads", response_model=UploadOut)
async def upload_file(admin: AdminDep, file: UploadFile = File(...)) -> UploadOut:
    del admin
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
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return UploadOut(file_name=file_name, file_path=str(path), size=size)
