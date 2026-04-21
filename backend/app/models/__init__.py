from app.models.chunk import Chunk  # noqa: F401 — registers table in SQLModel.metadata
from app.models.document import Document  # noqa: F401 — registers table in SQLModel.metadata

__all__ = ["Chunk", "Document"]
