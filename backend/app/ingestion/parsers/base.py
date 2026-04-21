from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedContent:
    text: str
    structure_hints: dict = field(default_factory=dict)


class Parser(ABC):
    @abstractmethod
    async def parse(self, data: bytes, filename: str) -> ParsedContent: ...
