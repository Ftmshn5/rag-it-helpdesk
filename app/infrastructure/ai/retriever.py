"""RAG'in "R"si: talebe anlamca en yakın bilgi bankası parçalarını bulur.

pgvector'ün kosinüs uzaklığı operatörü (<=>) kullanılır; 11a'daki HNSW indeksi
bu sorguyu hızlandırır. Benzerlik = 1 - uzaklık (1: aynı yön, 0: ilgisiz).
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import KnowledgeChunkModel, KnowledgeDocumentModel


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    document_title: str
    file_path: str  # yanıtta kaynak olarak gösterilir, örn. "knowledge/yazici-sorunlari.md"
    similarity: float


class KnowledgeRetriever(ABC):
    @abstractmethod
    def search(self, query_embedding: list[float], limit: int) -> list[RetrievedChunk]:
        """En benzer parçaları benzerliğe göre azalan sırada döndürür."""


class PgVectorRetriever(KnowledgeRetriever):
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def search(self, query_embedding: list[float], limit: int) -> list[RetrievedChunk]:
        distance = KnowledgeChunkModel.embedding.cosine_distance(query_embedding)
        statement = (
            select(
                KnowledgeChunkModel.content,
                KnowledgeDocumentModel.title,
                KnowledgeDocumentModel.file_path,
                distance.label("distance"),
            )
            .join(KnowledgeDocumentModel)
            .where(KnowledgeChunkModel.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )
        with self.session_factory() as session:
            rows = session.execute(statement).all()
        return [
            RetrievedChunk(
                content=row.content,
                document_title=row.title,
                file_path=row.file_path,
                similarity=1.0 - float(row.distance),
            )
            for row in rows
        ]
