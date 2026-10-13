"""Ollama (yerel model sunucusu) için strateji implementasyonları.

Ollama REST API'si:
- POST /api/embed  {"model", "input": [metinler]}        → {"embeddings": [[...], ...]}
- POST /api/chat   {"model", "messages", "stream": false} → {"message": {"content": "..."}}

Ağ ve sunucu hataları tek tip AiProviderError'a çevrilir; üst katman (facade
ve AutoAnswerTicketHandler) yalnızca "AI başarısız" bilgisini görür ve talebi
eskale eder.
"""

from typing import Any

import httpx

from app.infrastructure.ai.providers import AiProviderError, EmbeddingProvider, LlmProvider


class _OllamaClient:
    """Ortak HTTP kısmı. Testlerde sahte taşıyıcılı bir httpx.Client verilebilir."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float, client: httpx.Client | None) -> None:
        self.model = model
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout_seconds)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=payload)
        except httpx.TimeoutException as error:
            raise AiProviderError(f"Ollama zaman aşımına uğradı ({self.model}).") from error
        except httpx.HTTPError as error:
            raise AiProviderError(f"Ollama'ya ulaşılamadı: {error}") from error

        if response.status_code != 200:
            # Örn. 404: model indirilmemiş ("ollama pull <model>" gerekir)
            detail = self._error_detail(response)
            raise AiProviderError(f"Ollama hata döndürdü ({response.status_code}): {detail}")
        try:
            return response.json()
        except ValueError as error:
            raise AiProviderError("Ollama geçersiz JSON döndürdü.") from error

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        try:
            return str(response.json().get("error", response.text))
        except ValueError:
            return response.text


class OllamaEmbeddingProvider(_OllamaClient, EmbeddingProvider):
    """Strategy deseni — Concrete Strategy: yerel Ollama sunucusundaki embedding modeli (/api/embed)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        dimension: int,
        timeout_seconds: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(base_url, model, timeout_seconds, client)
        # Veritabanındaki vector sütununun boyutu: farklı boyutta vektör yazılmasın
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self._post("/api/embed", {"model": self.model, "input": texts})
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise AiProviderError("Ollama beklenen sayıda embedding döndürmedi.")
        for vector in embeddings:
            if len(vector) != self.dimension:
                raise AiProviderError(
                    f"'{self.model}' {len(vector)} boyutlu vektör döndürdü; "
                    f"veritabanı {self.dimension} boyut bekliyor."
                )
        return embeddings


class OllamaLlmProvider(_OllamaClient, LlmProvider):
    """Strategy deseni — Concrete Strategy: yerel Ollama sunucusundaki dil modeli (/api/chat)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_seconds: float = 120.0,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(base_url, model, timeout_seconds, client)
        # Düşük sıcaklık: yanıt bilgi bankasına sadık kalsın, "yaratıcı" olmasın
        self.temperature = temperature
        # CPU'da süre üretilen token sayısıyla doğru orantılı; üst sınır süreyi de sınırlar
        self.max_tokens = max_tokens

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        options: dict[str, Any] = {"temperature": self.temperature}
        if self.max_tokens is not None:
            options["num_predict"] = self.max_tokens
        data = self._post(
            "/api/chat",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": options,
            },
        )
        content = (data.get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise AiProviderError("Ollama boş yanıt döndürdü.")
        return content.strip()
