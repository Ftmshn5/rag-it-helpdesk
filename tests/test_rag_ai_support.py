"""RagAiSupport (Facade): alt sistemler sahte; veritabanı ve Ollama gerekmez.

Facade'ın işi alt sistemleri doğru sırayla çağırmak ve sonucu AutoAnswer'a
çevirmektir; testler bu orkestrasyonu ve güven skoru kurallarını doğrular.
"""

import pytest

from app.core import dependencies
from app.core.config import Settings
from app.domain.enums import TicketCategory
from app.domain.ticket import Ticket
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.ai.prompting import (
    NO_ANSWER_MARKER,
    SYSTEM_PROMPT,
    PromptBuilder,
)
from app.infrastructure.ai.providers import AiProviderError, EmbeddingProvider, LlmProvider
from app.infrastructure.ai.rag_ai_support import (
    NO_ANSWER_CONFIDENCE,
    NO_ANSWER_TEXT,
    RagAiSupport,
    SimilarityConfidence,
)
from app.infrastructure.ai.retriever import KnowledgeRetriever, RetrievedChunk


class FakeEmbedder(EmbeddingProvider):
    def __init__(self, fail: bool = False) -> None:
        self.texts: list[str] = []
        self.fail = fail

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise AiProviderError("Ollama'ya ulaşılamadı")
        self.texts.extend(texts)
        return [[0.5, 0.5] for _ in texts]


class FakeRetriever(KnowledgeRetriever):
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        self.limits: list[int] = []

    def search(self, query_embedding: list[float], limit: int) -> list[RetrievedChunk]:
        self.limits.append(limit)
        return self.chunks[:limit]


class FakeLlmProvider(LlmProvider):
    def __init__(self, answer: str = "Kağıdı çıkarın ve yazıcıyı yeniden açın.") -> None:
        self.answer = answer
        self.prompts: list[tuple[str, str]] = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append((system_prompt, user_prompt))
        return self.answer


def chunk(file_path: str, similarity: float, content: str = "Yazıcı > Kağıt sıkışması\n\nKapağı açın.") -> RetrievedChunk:
    return RetrievedChunk(content=content, document_title="Yazıcı", file_path=file_path, similarity=similarity)


TICKET = Ticket(
    id=7,
    title="Yazıcı kağıt sıkıştırıyor",
    description="B2 katındaki yazıcı sürekli kağıt sıkışması uyarısı veriyor.",
    category=TicketCategory.HARDWARE,
    requester_id=1,
)
CONFIDENCE = SimilarityConfidence(floor=0.45, ceiling=0.75)


def make_rag(chunks, chat=None, embedder=None):
    return RagAiSupport(
        embedder=embedder or FakeEmbedder(),
        retriever=FakeRetriever(chunks),
        llm=chat or FakeLlmProvider(),
        confidence=CONFIDENCE,
        top_k=3,
    )


# --- Güven skoru ---


@pytest.mark.parametrize(
    ("similarity", "expected"),
    [(0.30, 0.0), (0.45, 0.0), (0.60, 0.5), (0.75, 1.0), (0.90, 1.0)],
)
def test_similarity_is_mapped_linearly_between_floor_and_ceiling(similarity, expected):
    assert CONFIDENCE.score(similarity) == pytest.approx(expected)


def test_threshold_point_corresponds_to_a_concrete_similarity():
    # Sunum için: eşik 0.6 ⇔ benzerlik 0.63 (0.45 + 0.6 * 0.30)
    assert CONFIDENCE.score(0.63) == pytest.approx(0.6)


@pytest.mark.parametrize(("floor", "ceiling"), [(0.8, 0.5), (0.5, 0.5), (-0.1, 0.5), (0.5, 1.2)])
def test_invalid_confidence_settings_are_rejected(floor, ceiling):
    with pytest.raises(ValueError):
        SimilarityConfidence(floor=floor, ceiling=ceiling)


# --- Orkestrasyon ---


def test_answer_uses_llm_text_and_top_similarity_for_confidence():
    chat = FakeLlmProvider()
    rag = make_rag([chunk("knowledge/yazici-sorunlari.md", 0.70), chunk("knowledge/yazici-sorunlari.md", 0.60)], chat)

    answer = rag.try_auto_resolve(TICKET)

    assert answer.answer == "Kağıdı çıkarın ve yazıcıyı yeniden açın."
    assert answer.confidence == pytest.approx(CONFIDENCE.score(0.70))
    # Aynı dokümandan iki parça: kaynak bir kez
    # Aynı dokümandan iki parça: tek kaynak, iki alıntı (E4)
    [source] = answer.sources
    assert (source.title, source.file_path, len(source.excerpts)) == ("Yazıcı", "knowledge/yazici-sorunlari.md", 2)


def test_ticket_title_and_description_are_embedded_and_top_k_is_used():
    embedder = FakeEmbedder()
    retriever = FakeRetriever([chunk("knowledge/a.md", 0.7)])
    rag = RagAiSupport(
        embedder=embedder, retriever=retriever, llm=FakeLlmProvider(), confidence=CONFIDENCE, top_k=3
    )

    rag.try_auto_resolve(TICKET)

    assert embedder.texts == [f"{TICKET.title}\n\n{TICKET.description}"]
    assert retriever.limits == [3]


def test_irrelevant_chunks_are_not_given_to_llm_and_not_listed_as_sources():
    chat = FakeLlmProvider()
    rag = make_rag([chunk("knowledge/yazici.md", 0.70), chunk("knowledge/vpn.md", 0.40)], chat)

    answer = rag.try_auto_resolve(TICKET)

    _, user_prompt = chat.prompts[0]
    assert "knowledge/yazici.md" in user_prompt
    assert "knowledge/vpn.md" not in user_prompt
    assert [s.file_path for s in answer.sources] == ["knowledge/yazici.md"]


def test_no_relevant_chunk_skips_llm_and_returns_zero_confidence():
    chat = FakeLlmProvider()
    rag = make_rag([chunk("knowledge/vpn.md", 0.30)], chat)

    answer = rag.try_auto_resolve(TICKET)

    assert chat.prompts == []  # yavaş LLM çağrısı yapılmadı
    assert answer.confidence == 0.0
    assert answer.answer == NO_ANSWER_TEXT
    assert answer.sources == []


def test_llm_no_answer_marker_lowers_confidence_below_threshold():
    rag = make_rag([chunk("knowledge/yazici.md", 0.74)], FakeLlmProvider(answer=NO_ANSWER_MARKER))

    answer = rag.try_auto_resolve(TICKET)

    assert answer.confidence == NO_ANSWER_CONFIDENCE
    assert answer.confidence < 0.6
    assert answer.answer == NO_ANSWER_TEXT


@pytest.mark.parametrize(
    "text, expected",
    [
        ("BILGI_YOK", True),
        ("Bilgi_YOK\n\nParçalarda otopark izni yok.", True),  # qwen2.5:3b'de gözlendi
        ("BİLGİ YOK", True),
        ("bilgiyok", True),
        ("1. Yazıcıyı kapatın.\n2. Sıkışan kağıdı çıkarın.", False),
        ("Bilgilerinizi kontrol edin.", False),
    ],
)
def test_no_answer_marker_is_recognized_in_its_variants(text, expected):
    assert PromptBuilder.is_no_answer(text) is expected


def test_marker_variant_from_llm_also_lowers_confidence():
    rag = make_rag([chunk("knowledge/yazici.md", 0.74)], FakeLlmProvider(answer="Bilgi_YOK\n\nİlgili bilgi yok."))
    assert rag.try_auto_resolve(TICKET).confidence == NO_ANSWER_CONFIDENCE


def test_provider_errors_propagate_so_the_handler_can_escalate():
    rag = make_rag([chunk("knowledge/yazici.md", 0.7)], embedder=FakeEmbedder(fail=True))

    with pytest.raises(AiProviderError):
        rag.try_auto_resolve(TICKET)


# --- Prompt ---


def test_prompt_contains_numbered_sources_ticket_and_category():
    chunks = [chunk("knowledge/a.md", 0.7, "A > Bölüm\n\nMetin A"), chunk("knowledge/b.md", 0.6, "B\n\nMetin B")]

    system_prompt, user_prompt = PromptBuilder().build(TICKET, chunks)

    assert system_prompt == SYSTEM_PROMPT
    assert NO_ANSWER_MARKER in system_prompt
    assert "[1] Kaynak: knowledge/a.md\nA > Bölüm\n\nMetin A" in user_prompt
    assert "[2] Kaynak: knowledge/b.md" in user_prompt
    assert "Kategori: Donanım" in user_prompt
    assert f"Başlık: {TICKET.title}" in user_prompt
    assert f"Açıklama: {TICKET.description}" in user_prompt


# --- Kompozisyon kökü: AI_PROVIDER seçimi ---


def settings_with(provider: str) -> Settings:
    # _env_file=None: geliştiricinin .env'indeki model/eşik ayarları testi etkilemesin
    return Settings(_env_file=None, database_url="postgresql+psycopg://x:y@localhost/z", ai_provider=provider)


def test_fake_provider_is_selected_by_default(monkeypatch):
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings_with("fake"))
    assert isinstance(dependencies.get_ai_support.__wrapped__(), FakeAiSupport)


def test_rag_provider_is_wired_with_ollama_strategies(monkeypatch):
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings_with("rag"))

    ai_support = dependencies.get_ai_support.__wrapped__()

    assert isinstance(ai_support, RagAiSupport)
    assert ai_support.embedder.model == "bge-m3"
    assert ai_support.embedder.dimension == 1024
    assert ai_support.llm.model == "qwen2.5:3b"
    assert ai_support.llm.max_tokens == 300
    assert ai_support.confidence == SimilarityConfidence(floor=0.50, ceiling=0.64)
