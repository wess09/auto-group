import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from app.schemas.rpc import BrowseInput, PageResult
from app.services import onebot


cache: dict[tuple[int, str], tuple[float, list[dict]]] = {}


@dataclass
class DirectoryLock:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0


locks: dict[tuple[int, str], DirectoryLock] = {}


@asynccontextmanager
async def directory_lock(key):
    entry = locks.setdefault(key, DirectoryLock())
    entry.users += 1
    try:
        async with entry.lock:
            yield
    finally:
        entry.users -= 1
        if not entry.users:
            locks.pop(key, None)


def invalidate(group_id: int) -> None:
    for key in list(cache):
        if key[0] == group_id:
            cache.pop(key, None)


async def browse(params: BrowseInput) -> PageResult:
    key = (params.group_id, params.folder_id)
    async with directory_lock(key):
        saved = cache.get(key)
        if not saved or saved[0] <= time.monotonic():
            result = await (
                onebot.get_group_files_by_folder(*key)
                if key[1]
                else onebot.get_group_root_files(key[0])
            )
            result = result if isinstance(result, dict) else {"files": result}
            folders = [
                {
                    "type": "folder",
                    "folder_id": row.get("folder_id", row.get("id", "")),
                    "name": row.get("folder_name", row.get("name", "目录")),
                }
                for row in result.get("folders", [])
            ]
            files = [
                {
                    "type": "file",
                    "file_id": row.get("file_id", row.get("id", "")),
                    "name": row.get("file_name", row.get("name", "文件")),
                    "size": row.get("file_size", row.get("size", 0)),
                    "busid": row.get("busid", 0),
                    "upload_time": row.get("upload_time"),
                }
                for row in result.get("files", [])
            ]
            rows = sorted(
                folders + files,
                key=lambda row: (
                    row["type"] != "folder",
                    row["name"],
                    str(row.get("file_id", row.get("folder_id"))),
                ),
            )
            if len(cache) >= 128:
                oldest = min(cache, key=lambda entry: cache[entry][0])
                cache.pop(oldest)
            cache[key] = (time.monotonic() + 30, rows)
            saved = cache[key]
    rows = [row for row in saved[1] if params.q.casefold() in row["name"].casefold()]
    offset = (params.page - 1) * params.page_size
    return PageResult(
        items=rows[offset : offset + params.page_size],
        total=len(rows),
        page=params.page,
        page_size=params.page_size,
    )
