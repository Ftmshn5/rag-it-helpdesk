"""Dosya depolama arayüzü.

Application katmanı dosyanın yerel diskte mi, bir bulut depolamada mı
durduğunu bilmez. Şimdilik yerel disk kullanılıyor (infrastructure/storage);
ileride örneğin S3'e geçmek yalnızca yeni bir implementasyon yazmayı gerektirir.
"""

from abc import ABC, abstractmethod


class FileStorage(ABC):
    @abstractmethod
    def save(self, content: bytes, *, folder: str, extension: str) -> str:
        """İçeriği kaydeder ve depolama içindeki göreli yolunu döndürür.

        Dosya adı depolama tarafından üretilir; istemcinin verdiği ad kullanılmaz.
        """

    @abstractmethod
    def read(self, path: str) -> bytes:
        """Kaydedilmiş dosyanın içeriği; dosya yoksa FileNotFoundError."""

    @abstractmethod
    def delete(self, path: str) -> None: ...
