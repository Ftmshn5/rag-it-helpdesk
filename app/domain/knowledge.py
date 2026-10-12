"""Bilgi bankası varlıkları (RAG dokümanları ve parçaları)."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(kw_only=True)
class KnowledgeDocument:
    id: int | None = None
    title: str
    file_path: str
    indexed_at: datetime | None = None


@dataclass(kw_only=True)
class KnowledgeChunk:
    id: int | None = None
    document_id: int
    content: str
    # pgvector'deki vektörün domain'deki karşılığı: düz bir float listesi
    embedding: list[float] | None = field(default=None, repr=False)
