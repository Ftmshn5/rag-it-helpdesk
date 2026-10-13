"""AI destek arayüzü: Facade deseni.

Bir talebe otomatik yanıt üretmek, arka planda birçok alt sistemin birlikte
çalışmasını gerektirir (gerçek RAG'de):

    embedding servisi → pgvector retriever → prompt builder → LLM istemcisi (Ollama)

Uygulamanın geri kalanı bu alt sistemlerin hiçbirini tanımaz; yalnızca bu
arayüzün tek metodunu çağırır. Böylece:
- Command handler'lar RAG'in karmaşıklığından korunur.
- Şimdilik FakeAiSupport, 11. adımda gerçek RAG implementasyonu kullanılır;
  geçiş sırasında application ve domain katmanında hiçbir değişiklik olmaz.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.domain.ticket import Ticket


@dataclass(frozen=True)
class AutoAnswer:
    answer: str
    # 0.0 - 1.0 arası; iş kuralı 4'teki eşikle karşılaştırılır
    confidence: float
    # Yanıtın dayandığı bilgi bankası dokümanları (kullanıcıya kaynak olarak gösterilir)
    sources: list[str] = field(default_factory=list)


class AiSupportFacade(ABC):
    """Facade deseni — Facade: RAG alt sistemlerini (embedding, retriever, istem, LLM) tek bir metodun arkasında gizler."""

    @abstractmethod
    def try_auto_resolve(self, ticket: Ticket) -> AutoAnswer:
        """Talebe bilgi bankasına dayanarak bir çözüm önerisi üretir."""
