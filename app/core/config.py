"""Uygulama ayarları.

Tüm yapılandırma tek bir yerden, ortam değişkenlerinden / .env dosyasından okunur.
Kodun içinde sabit bağlantı adresi veya şifre bulunmaz.
"""

from functools import lru_cache
from pathlib import Path

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

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Ayarları bir kez oluşturur ve sonraki çağrılarda aynı nesneyi döndürür."""
    return Settings()
