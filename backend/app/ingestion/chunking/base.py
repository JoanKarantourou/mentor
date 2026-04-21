from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TextChunk:
    text: str
    token_count: int
    meta: dict


class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, text: str) -> list[TextChunk]: ...
