"""Bilgi bankası indeksleme: gerçek veritabanı (pgvector), sahte embedding sağlayıcısı."""

from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.infrastructure.ai.chunking import MarkdownChunker
from app.infrastructure.ai.indexing import KnowledgeIndexer
from app.infrastructure.ai.providers import AiProviderError, EmbeddingProvider
from app.infrastructure.db.models import (
    EMBEDDING_DIMENSION,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)


class FakeEmbedder(EmbeddingProvider):
    """Metin uzunluğundan türetilen deterministik vektörler; çağrıları kaydeder."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.fail = fail

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.fail:
            raise AiProviderError("Ollama'ya ulaşılamadı")
        return [[float(len(text) % 7 + 1)] + [0.0] * (EMBEDDING_DIMENSION - 1) for text in texts]


@pytest.fixture(autouse=True)
def empty_knowledge_base(session_factory):
    """Geliştirme veritabanındaki gerçek indeks testi etkilemesin (sonda geri alınır)."""
    with session_factory() as session, session.begin():
        session.execute(delete(KnowledgeDocumentModel))


def write(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


TWO_SECTIONS = "# Yazıcı\n\n## Kağıt sıkışması\n\nKapağı açın.\n\n## Toner\n\nSekreterliğe haber verin.\n"


def chunks_of(session_factory, file_path: str) -> list[KnowledgeChunkModel]:
    with session_factory() as session:
        return list(
            session.scalars(
                select(KnowledgeChunkModel)
                .join(KnowledgeDocumentModel)
                .where(KnowledgeDocumentModel.file_path == file_path)
                .order_by(KnowledgeChunkModel.id)
            )
        )


def document_paths(session_factory) -> set[str]:
    with session_factory() as session:
        return set(session.scalars(select(KnowledgeDocumentModel.file_path)))


def test_index_directory_stores_document_and_embedded_chunks(session_factory, tmp_path):
    write(tmp_path, "yazici.md", TWO_SECTIONS)

    results, removed = KnowledgeIndexer(session_factory, FakeEmbedder(), MarkdownChunker()).index_directory(tmp_path)

    assert [(r.file_path, r.title, r.chunk_count) for r in results] == [("knowledge/yazici.md", "Yazıcı", 2)]
    assert removed == []
    chunks = chunks_of(session_factory, "knowledge/yazici.md")
    assert [chunk.content for chunk in chunks] == [
        "Yazıcı > Kağıt sıkışması\n\nKapağı açın.",
        "Yazıcı > Toner\n\nSekreterliğe haber verin.",
    ]
    assert all(len(chunk.embedding) == EMBEDDING_DIMENSION for chunk in chunks)
    with session_factory() as session:
        indexed_at = session.scalar(
            select(KnowledgeDocumentModel.indexed_at).where(
                KnowledgeDocumentModel.file_path == "knowledge/yazici.md"
            )
        )
        assert indexed_at is not None


def test_reindexing_replaces_chunks_instead_of_duplicating(session_factory, tmp_path):
    path = write(tmp_path, "yazici.md", TWO_SECTIONS)
    indexer = KnowledgeIndexer(session_factory, FakeEmbedder(), MarkdownChunker())
    indexer.index_directory(tmp_path)

    path.write_text("# Yazıcı (güncel)\n\n## Tek bölüm\n\nYeni içerik.\n", encoding="utf-8")
    indexer.index_directory(tmp_path)

    chunks = chunks_of(session_factory, "knowledge/yazici.md")
    assert [chunk.content for chunk in chunks] == ["Yazıcı (güncel) > Tek bölüm\n\nYeni içerik."]
    with session_factory() as session:
        count = session.scalar(
            select(func.count()).where(KnowledgeDocumentModel.file_path == "knowledge/yazici.md")
        )
        assert count == 1


def test_deleted_file_is_removed_with_its_chunks(session_factory, tmp_path):
    write(tmp_path, "yazici.md", TWO_SECTIONS)
    old = write(tmp_path, "eski.md", "# Eski\n\n## Bölüm\n\nMetin.\n")
    indexer = KnowledgeIndexer(session_factory, FakeEmbedder(), MarkdownChunker())
    indexer.index_directory(tmp_path)

    old.unlink()
    _, removed = indexer.index_directory(tmp_path)

    assert removed == ["knowledge/eski.md"]
    assert "knowledge/eski.md" not in document_paths(session_factory)
    assert chunks_of(session_factory, "knowledge/eski.md") == []


def test_embedding_failure_leaves_existing_index_untouched(session_factory, tmp_path):
    path = write(tmp_path, "yazici.md", TWO_SECTIONS)
    KnowledgeIndexer(session_factory, FakeEmbedder(), MarkdownChunker()).index_directory(tmp_path)
    before = [chunk.content for chunk in chunks_of(session_factory, "knowledge/yazici.md")]

    path.write_text("# Yazıcı\n\n## Yeni\n\nYeni içerik.\n", encoding="utf-8")
    with pytest.raises(AiProviderError):
        KnowledgeIndexer(session_factory, FakeEmbedder(fail=True), MarkdownChunker()).index_directory(tmp_path)

    assert [chunk.content for chunk in chunks_of(session_factory, "knowledge/yazici.md")] == before


def test_chunks_are_embedded_in_batches(session_factory, tmp_path):
    sections = "".join(f"## Bölüm {i}\n\nMetin {i}.\n\n" for i in range(5))
    write(tmp_path, "uzun.md", f"# Uzun\n\n{sections}")
    embedder = FakeEmbedder()

    KnowledgeIndexer(session_factory, embedder, MarkdownChunker(), batch_size=2).index_directory(tmp_path)

    assert [len(batch) for batch in embedder.calls] == [2, 2, 1]
    assert len(chunks_of(session_factory, "knowledge/uzun.md")) == 5
