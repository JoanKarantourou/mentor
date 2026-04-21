from app.config import settings
from app.storage.base import BlobStore
from app.storage.local import LocalBlobStore


def create_blob_store() -> BlobStore:
    match settings.BLOB_STORE:
        case "local":
            return LocalBlobStore(root=settings.BLOB_STORE_ROOT)
        case _:
            raise ValueError(f"Unknown blob store: {settings.BLOB_STORE!r}")
