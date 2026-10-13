"""Bilgi bankası indeksleme: Markdown dokümanı → parçalar → embedding → pgvector.

Çalıştırma (Ollama açık ve embedding modeli indirilmiş olmalı):
    python -m app.infrastructure.ai.indexing

İdempotenttir: aynı komut tekrar çalıştırılabilir. Her doküman için eski
parçalar silinip yenileri yazılır; klasörden silinen dokümanlar veritabanından
da kaldırılır. Bilgi bankası küçük olduğu için değişmeyen dosyaları atlama
(içerik özeti karşılaştırma) gibi bir optimizasyon yapılmadı.

Bu modül bir bakım aracıdır (projections.py'deki yeniden kurma komutu gibi),
bu yüzden doğrudan SQLAlchemy oturumuyla çalışır. "Bilgi bankasına doküman
ekle" (UC-13) bir kullanıcı işlemi olarak eklenirse application katmanında bir
command'a ve bir arayüze dönüşür; parçalama ve embedding mantığı aynen kullanılır.
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.clock import Clock
from app.infrastructure.ai.chunking import MarkdownChunker
from app.infrastructure.ai.providers import AiProviderError, EmbeddingProvider
from app.infrastructure.db.models import KnowledgeChunkModel, KnowledgeDocumentModel

# Veritabanında saklanan ve yanıtta kaynak olarak gösterilen yol öneki
SOURCE_PREFIX = "knowledge/"


@dataclass(frozen=True)
class IndexResult:
    file_path: str
    title: str
    chunk_count: int


class KnowledgeIndexer:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        embedder: EmbeddingProvider,
        chunker: MarkdownChunker,
        *,
        batch_size: int = 16,
    ) -> None:
        self._session_factory = session_factory
        self._embedder = embedder
        self._chunker = chunker
        self._batch_size = batch_size

    def index_directory(self, directory: Path) -> tuple[list[IndexResult], list[str]]:
        """Klasördeki tüm .md dosyalarını indeksler; silinmiş dosyaların kayıtlarını kaldırır.

        Dönüş: (indekslenen dokümanlar, kaldırılan doküman yolları)
        """
        results = [self.index_file(path) for path in sorted(directory.glob("*.md"))]
        removed = self._remove_missing({result.file_path for result in results})
        return results, removed

    def index_file(self, path: Path) -> IndexResult:
        file_path = SOURCE_PREFIX + path.name
        document = self._chunker.parse(path.read_text(encoding="utf-8"), fallback_title=path.stem)

        # Önce tüm vektörler hesaplanır, sonra tek transaction'da yazılır:
        # Ollama yarıda hata verirse veritabanındaki eski indeks bozulmaz.
        contents = [chunk.content for chunk in document.chunks]
        embeddings = self._embed_in_batches(contents)

        with self._session_factory() as session, session.begin():
            model = session.scalar(
                select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.file_path == file_path)
            )
            if model is None:
                model = KnowledgeDocumentModel(file_path=file_path, title=document.title)
                session.add(model)
                session.flush()  # id gerekli
            else:
                model.title = document.title
                session.execute(
                    delete(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == model.id)
                )
            session.add_all(
                KnowledgeChunkModel(document_id=model.id, content=content, embedding=embedding)
                for content, embedding in zip(contents, embeddings, strict=True)
            )
            model.indexed_at = Clock.now()

        return IndexResult(file_path=file_path, title=document.title, chunk_count=len(contents))

    def _embed_in_batches(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            vectors.extend(self._embedder.embed(texts[start : start + self._batch_size]))
        return vectors

    def _remove_missing(self, existing_paths: set[str]) -> list[str]:
        with self._session_factory() as session, session.begin():
            stale = session.scalars(
                select(KnowledgeDocumentModel).where(
                    KnowledgeDocumentModel.file_path.startswith(SOURCE_PREFIX),
                    KnowledgeDocumentModel.file_path.not_in(existing_paths),
                )
            ).all()
            for model in stale:
                session.delete(model)  # parçalar ON DELETE CASCADE ile silinir
            return [model.file_path for model in stale]


def main() -> int:
    # Komut satırı aracı: bağımlılıklar burada, uygulamanın kompozisyon köküne benzer şekilde kurulur
    from app.core.config import get_settings
    from app.infrastructure.ai.ollama import OllamaEmbeddingProvider
    from app.infrastructure.db.models import EMBEDDING_DIMENSION
    from app.infrastructure.db.session import Database

    settings = get_settings()
    embedder = OllamaEmbeddingProvider(
        settings.ollama_base_url,
        settings.embedding_model,
        dimension=EMBEDDING_DIMENSION,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
    indexer = KnowledgeIndexer(Database(settings.database_url).session_factory, embedder, MarkdownChunker())

    try:
        results, removed = indexer.index_directory(settings.knowledge_dir)
    except AiProviderError as error:
        print(f"İndeksleme başarısız: {error}", file=sys.stderr)
        print(f"Ollama açık mı ve '{settings.embedding_model}' indirildi mi? (ollama pull {settings.embedding_model})", file=sys.stderr)
        return 1

    for result in results:
        print(f"{result.file_path}: {result.chunk_count} parça  ({result.title})")
    for file_path in removed:
        print(f"{file_path}: dosya yok, kaldırıldı")
    print(f"Toplam {len(results)} doküman, {sum(r.chunk_count for r in results)} parça indekslendi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
