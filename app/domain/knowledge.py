"""Bilgi bankası varlıkları (RAG dokümanları ve parçaları).

Not: İndeksleme bugün bir bakım aracı olarak doğrudan ORM modelleriyle çalışır
(infrastructure/ai/indexing.py). Bu sınıflar domain modelinin parçasıdır;
"bilgi bankasına doküman ekle" (UC-13) bir command olarak eklenirse kullanılır.
"""

from datetime import datetime

from app.domain.entity import Entity


class KnowledgeDocument(Entity):
    """Bilgi bankasındaki bir Markdown dokümanı."""

    def __init__(
        self, *, id: int | None = None, title: str, file_path: str, indexed_at: datetime | None = None
    ) -> None:
        super().__init__(id)
        self._title = title
        self._file_path = file_path
        self._indexed_at = indexed_at

    @property
    def title(self) -> str:
        return self._title

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def indexed_at(self) -> datetime | None:
        return self._indexed_at

    @property
    def is_indexed(self) -> bool:
        return self._indexed_at is not None

    def mark_indexed(self, at: datetime) -> None:
        self._indexed_at = at


class KnowledgeChunk(Entity):
    """Dokümanın embedding'i hesaplanan bir parçası."""

    def __init__(
        self, *, id: int | None = None, document_id: int, content: str, embedding: list[float] | None = None
    ) -> None:
        super().__init__(id)
        self._document_id = document_id
        self._content = content
        # pgvector'deki vektörün domain'deki karşılığı: düz bir float listesi
        self._embedding = embedding

    @property
    def document_id(self) -> int:
        return self._document_id

    @property
    def content(self) -> str:
        return self._content

    @property
    def embedding(self) -> list[float] | None:
        return self._embedding
