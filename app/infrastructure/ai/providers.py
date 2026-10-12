"""RAG alt sistemlerinin model sağlayıcıları: Strategy deseni.

RAG iki ayrı modele ihtiyaç duyar:
- EmbeddingProvider: metni vektöre çevirir (bilgi bankası parçaları ve talep metni).
- ChatModel: bulunan parçalara dayanarak yanıt metnini üretir.

Her biri bir "strateji" arayüzüdür; somut sağlayıcı (bugün Ollama, yarın başka
bir yerel/bulut servis) çalışma zamanında, kompozisyon kökünde seçilir. RAG
kodu (retriever, facade) yalnızca bu arayüzleri tanır.

Bu arayüzler bilerek application/interfaces'te değil burada: uygulamanın geri
kalanı yalnızca AiSupportFacade'ı bilir (Facade deseni). Embedding ve LLM,
Facade'ın arkasında gizlenen alt sistemlerin iç ayrıntısıdır.
"""

from abc import ABC, abstractmethod


class AiProviderError(Exception):
    """Model sağlayıcısına ulaşılamadı veya beklenmeyen yanıt döndü."""


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Her metin için bir vektör döndürür (girdiyle aynı sırada)."""


class ChatModel(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Sistem talimatı ve kullanıcı istemiyle yanıt metni üretir."""
