"""Gerçek RAG implementasyonu: AiSupportFacade'ın arkasındaki alt sistemleri birleştirir.

    talep metni ──embed──▶ vektör ──retriever──▶ en yakın parçalar
        ──prompt builder──▶ istem ──chat model──▶ yanıt + güven skoru

Facade deseni: uygulamanın geri kalanı (AutoAnswerTicketHandler) yalnızca
try_auto_resolve(ticket) çağırır; bu dört alt sistemin hiçbirini tanımaz.
FakeAiSupport'tan buna geçişte application ve domain katmanında değişiklik yoktur.

Güven skoru (iş kuralı 4) retrieval benzerliğinden hesaplanır, LLM'in kendi
beyanından değil: en iyi parçanın kosinüs benzerliği ölçülebilir ve
tekrarlanabilirdir. LLM "bilgi yok" işaretini verirse skor düşürülür.
"""

import logging
from dataclasses import dataclass

from app.application.interfaces.ai_support import AiSupportFacade, AutoAnswer
from app.domain.ticket import Ticket
from app.infrastructure.ai.prompting import PromptBuilder, is_no_answer
from app.infrastructure.ai.providers import LlmProvider, EmbeddingProvider
from app.infrastructure.ai.retriever import KnowledgeRetriever, RetrievedChunk

logger = logging.getLogger(__name__)

NO_ANSWER_TEXT = "Bilgi bankasında bu sorunla ilgili yeterli bilgi bulunamadı."
# LLM bilgi yetmediğini söylediğinde verilen skor: eşiğin her zaman altında kalır
NO_ANSWER_CONFIDENCE = 0.1


@dataclass(frozen=True)
class SimilarityConfidence:
    """Kosinüs benzerliğini 0-1 güven skoruna doğrusal olarak çevirir.

    floor ve altı → 0 (ilgisiz; bu parçalar LLM'e hiç verilmez)
    ceiling ve üstü → 1 (bilgi bankasında neredeyse birebir karşılığı var)

    Embedding modelleri ilgisiz metinlere de 0'dan büyük benzerlik verdiği için
    ham benzerlik doğrudan güven skoru olarak kullanılmaz. floor/ceiling,
    gerçek modelle örnek taleplerin benzerlikleri ölçülerek ayarlanır (.env).
    """

    floor: float
    ceiling: float

    def __post_init__(self) -> None:
        if not 0 <= self.floor < self.ceiling <= 1:
            raise ValueError("Güven ayarı geçersiz: 0 <= floor < ceiling <= 1 olmalı.")

    def is_relevant(self, similarity: float) -> bool:
        return similarity > self.floor

    def score(self, similarity: float) -> float:
        ratio = (similarity - self.floor) / (self.ceiling - self.floor)
        return round(min(max(ratio, 0.0), 1.0), 2)


class RagAiSupport(AiSupportFacade):
    def __init__(
        self,
        *,
        embedder: EmbeddingProvider,
        retriever: KnowledgeRetriever,
        llm: LlmProvider,
        confidence: SimilarityConfidence,
        prompt_builder: PromptBuilder | None = None,
        top_k: int = 4,
    ) -> None:
        self.embedder = embedder
        self.retriever = retriever
        self.llm = llm
        self.confidence = confidence
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.top_k = top_k

    def try_auto_resolve(self, ticket: Ticket) -> AutoAnswer:
        # Sağlayıcı hataları (AiProviderError) bilerek yakalanmaz: handler yakalar ve talebi eskale eder.
        [query_vector] = self.embedder.embed([self.prompt_builder.embedding_query(ticket)])
        chunks = [
            chunk
            for chunk in self.retriever.search(query_vector, self.top_k)
            if self.confidence.is_relevant(chunk.similarity)
        ]
        if not chunks:
            # İlgili bilgi yok: yavaş LLM çağrısı hiç yapılmaz
            logger.info("Talep %s: ilgili bilgi bankası parçası bulunamadı", ticket.id)
            return AutoAnswer(answer=NO_ANSWER_TEXT, confidence=0.0, sources=[])

        system_prompt, user_prompt = self.prompt_builder.build(ticket, chunks)
        answer = self.llm.generate(system_prompt, user_prompt)
        sources = _unique_sources(chunks)

        if is_no_answer(answer):
            logger.info("Talep %s: LLM bilgi bankasını yetersiz buldu", ticket.id)
            return AutoAnswer(answer=NO_ANSWER_TEXT, confidence=NO_ANSWER_CONFIDENCE, sources=sources)

        confidence = self.confidence.score(chunks[0].similarity)
        logger.info(
            "Talep %s: en iyi benzerlik %.3f → güven %.2f", ticket.id, chunks[0].similarity, confidence
        )
        return AutoAnswer(answer=answer, confidence=confidence, sources=sources)


def _unique_sources(chunks: list[RetrievedChunk]) -> list[str]:
    # Aynı dokümandan birden fazla parça gelebilir; kaynak bir kez gösterilir (sıra korunur)
    return list(dict.fromkeys(chunk.file_path for chunk in chunks))
