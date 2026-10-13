"""Ollama strateji implementasyonları: gerçek sunucu olmadan, httpx.MockTransport ile.

Kontrol edilenler: doğru istek gövdesi, yanıtın ayrıştırılması ve her tür
hatanın (ağ, zaman aşımı, HTTP hatası, beklenmeyen yanıt) AiProviderError'a
çevrilmesi.
"""

import json

import httpx
import pytest

from app.infrastructure.ai.ollama import OllamaEmbeddingProvider, OllamaLlmProvider
from app.infrastructure.ai.providers import AiProviderError

BASE_URL = "http://ollama.test"


def client_with(handler) -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))


def embedder(handler, dimension: int = 3) -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider(BASE_URL, "bge-m3", dimension=dimension, client=client_with(handler))


def llm(handler) -> OllamaLlmProvider:
    return OllamaLlmProvider(BASE_URL, "qwen2.5:3b", client=client_with(handler))


# --- Embedding ---


def test_embed_sends_all_texts_in_one_request_and_returns_vectors_in_order():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]})

    vectors = embedder(handler).embed(["şifre", "yazıcı"])

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert len(requests) == 1
    assert requests[0].url.path == "/api/embed"
    assert json.loads(requests[0].content) == {"model": "bge-m3", "input": ["şifre", "yazıcı"]}


def test_embed_empty_list_makes_no_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("istek atılmamalıydı")

    assert embedder(handler).embed([]) == []


def test_embed_rejects_vectors_with_wrong_dimension():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]})

    with pytest.raises(AiProviderError, match="2 boyutlu"):
        embedder(handler, dimension=3).embed(["metin"])


def test_embed_rejects_missing_embeddings():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": []})

    with pytest.raises(AiProviderError, match="beklenen sayıda"):
        embedder(handler).embed(["metin"])


# --- Chat ---


def test_generate_sends_system_and_user_messages_without_streaming():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "  Yanıt.  "}})

    answer = llm(handler).generate("Sistem talimatı", "Soru")

    assert answer == "Yanıt."
    body = json.loads(requests[0].content)
    assert requests[0].url.path == "/api/chat"
    assert body["model"] == "qwen2.5:3b"
    assert body["stream"] is False
    assert body["messages"] == [
        {"role": "system", "content": "Sistem talimatı"},
        {"role": "user", "content": "Soru"},
    ]
    assert body["options"]["temperature"] == pytest.approx(0.1)


def test_generate_sends_token_limit_only_when_configured():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "Yanıt."}})

    OllamaLlmProvider(BASE_URL, "m", max_tokens=300, client=client_with(handler)).generate("s", "u")
    OllamaLlmProvider(BASE_URL, "m", client=client_with(handler)).generate("s", "u")

    assert bodies[0]["options"]["num_predict"] == 300
    assert "num_predict" not in bodies[1]["options"]


def test_generate_rejects_empty_answer():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "   "}})

    with pytest.raises(AiProviderError, match="boş yanıt"):
        llm(handler).generate("s", "u")


# --- Ortak hata çevirisi ---


def test_http_error_includes_ollama_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": 'model "qwen2.5:3b" not found, try pulling it first'})

    with pytest.raises(AiProviderError, match="404.*not found"):
        llm(handler).generate("s", "u")


def test_connection_error_becomes_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("bağlantı reddedildi", request=request)

    with pytest.raises(AiProviderError, match="ulaşılamadı"):
        embedder(handler).embed(["metin"])


def test_timeout_becomes_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("yavaş", request=request)

    with pytest.raises(AiProviderError, match="zaman aşımı"):
        llm(handler).generate("s", "u")


def test_invalid_json_becomes_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>")

    with pytest.raises(AiProviderError, match="geçersiz JSON"):
        llm(handler).generate("s", "u")
