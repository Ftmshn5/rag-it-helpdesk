"""PgVectorRetriever: gerçek pgvector sorgusu, elle seçilmiş vektörlerle.

Vektörler 1024 boyutlu ama yalnızca ilk iki bileşen dolu; böylece kosinüs
benzerlikleri elle hesaplanabilir.
"""

import math

import pytest
from sqlalchemy import delete

from app.infrastructure.ai.retriever import PgVectorRetriever
from app.infrastructure.db.models import (
    EMBEDDING_DIMENSION,
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)


def vector(x: float, y: float) -> list[float]:
    return [x, y] + [0.0] * (EMBEDDING_DIMENSION - 2)


@pytest.fixture
def knowledge(session_factory):
    with session_factory() as session, session.begin():
        # Geliştirme veritabanında gerçek indeks olabilir; test kendi verisiyle yalıtılır
        # (test transaction'ı sonunda geri alındığı için gerçek indeks etkilenmez)
        session.execute(delete(KnowledgeDocumentModel))
        printer = KnowledgeDocumentModel(title="Yazıcı", file_path="knowledge/test-yazici.md")
        vpn = KnowledgeDocumentModel(title="VPN", file_path="knowledge/test-vpn.md")
        session.add_all([printer, vpn])
        session.flush()
        session.add_all(
            [
                KnowledgeChunkModel(document_id=printer.id, content="aynı yön", embedding=vector(1, 0)),
                KnowledgeChunkModel(document_id=vpn.id, content="45 derece", embedding=vector(1, 1)),
                KnowledgeChunkModel(document_id=vpn.id, content="dik", embedding=vector(0, 1)),
                KnowledgeChunkModel(document_id=vpn.id, content="vektörsüz", embedding=None),
            ]
        )


def test_returns_nearest_chunks_by_cosine_similarity(session_factory, knowledge):
    ours = PgVectorRetriever(session_factory).search(vector(1, 0), limit=3)

    assert [r.content for r in ours] == ["aynı yön", "45 derece", "dik"]
    assert ours[0].similarity == pytest.approx(1.0)
    assert ours[1].similarity == pytest.approx(1 / math.sqrt(2))
    assert ours[2].similarity == pytest.approx(0.0, abs=1e-6)
    assert (ours[0].document_title, ours[0].file_path) == ("Yazıcı", "knowledge/test-yazici.md")


def test_limit_is_respected_and_chunks_without_embedding_are_skipped(session_factory, knowledge):
    results = PgVectorRetriever(session_factory).search(vector(0, 1), limit=10)

    assert "vektörsüz" not in [r.content for r in results]
    assert len(PgVectorRetriever(session_factory).search(vector(0, 1), limit=2)) == 2
