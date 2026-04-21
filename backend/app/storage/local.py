import asyncio
import os
from pathlib import Path

import aiofiles

from app.storage.base import BlobStore


class LocalBlobStore(BlobStore):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _resolve(self, key: str) -> Path:
        return self.root / key

    async def put(self, key: str, data: bytes, content_type: str) -> str:
        path = self._resolve(key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return key

    async def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Blob not found: {key!r}")
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            await asyncio.to_thread(os.remove, path)

    async def exists(self, key: str) -> bool:
        return self._resolve(key).exists()
