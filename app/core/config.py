"""Uygulama ayarları.

Tüm yapılandırma tek bir yerden, ortam değişkenlerinden / .env dosyasından okunur.
Kodun içinde sabit bağlantı adresi veya şifre bulunmaz.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # .env içindeki POSTGRES_* gibi yalnızca docker-compose'un kullandığı değişkenleri yok say
        extra="ignore",
    )

    app_name: str = "IT Destek ve Envanter Otomasyonu"
    debug: bool = False
    database_url: str

    # Ekran görüntüsü yükleme (iş kuralı 5)
    upload_dir: Path = Path("data/uploads")
    max_upload_size_mb: int = 5

    # İş kuralı 4: AI güven skoru bunun altındaysa talep doğrudan eskale edilir
    ai_confidence_threshold: float = 0.6

    # AI sağlayıcısı: "fake" (anahtar kelimeli sahte AI) veya "rag" (Ollama + pgvector)
    ai_provider: Literal["fake", "rag"] = "fake"
    # RAG bilgi bankası dokümanları (Markdown); indeksleme komutu bu klasörü okur
    knowledge_dir: Path = Path("data/knowledge")
    ollama_base_url: str = "http://127.0.0.1:11434"
    embedding_model: str = "bge-m3"
    llm_model: str = "qwen2.5:3b"
    # CPU'da çalışan model yavaş olabilir; aşılırsa AI hatası sayılır ve talep eskale edilir
    ollama_timeout_seconds: float = 180.0
    # Yanıt uzunluğu üst sınırı (token). CPU'da süreyi asıl belirleyen üretilen token sayısıdır
    llm_max_tokens: int = 300
    # Retriever'ın LLM'e verdiği en fazla parça sayısı
    rag_top_k: int = 4
    # Güven skoru = kosinüs benzerliğinin [floor, ceiling] aralığına doğrusal izdüşümü.
    # floor altındaki parçalar ilgisiz sayılır. bge-m3 ile ölçüldü (calibrate.py):
    # cevaplanabilir talepler 0.617-0.755, kapsam dışı 0.413-0.542 → eşik 0.6 ≈ benzerlik 0.58.
    rag_similarity_floor: float = 0.50
    rag_similarity_ceiling: float = 0.64

    # Frontend'in (Vite geliştirme sunucusu) API'ye tarayıcıdan erişebileceği adresler
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Ayarları bir kez oluşturur ve sonraki çağrılarda aynı nesneyi döndürür."""
    return Settings()
