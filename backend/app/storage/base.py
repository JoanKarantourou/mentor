from abc import ABC, abstractmethod


class BlobStore(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes, content_type: str) -> str:
        """Store bytes under key. Returns the key."""

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Retrieve bytes by key. Raises FileNotFoundError if missing."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete the blob at key. No-op if missing."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if the key exists."""
