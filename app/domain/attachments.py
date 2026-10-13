"""İş kuralı 5: ekran görüntüsü yalnızca png/jpg ve boyut sınırı altında kabul edilir.

Dosya türü istemcinin söylediğine (dosya adı uzantısı veya Content-Type
başlığı) göre değil, içeriğin ilk baytlarındaki imzaya ("magic bytes") göre
belirlenir. Uzantıyı değiştirmek kolaydır; içerik imzasını taklit etmek ise
dosyayı gerçekten o türde yapmayı gerektirir.
"""

from dataclasses import dataclass

from app.domain.errors import InvalidFileError


@dataclass(frozen=True)
class ImageType:
    """Değer nesnesi: kabul edilen bir görüntü türü."""

    mime_type: str
    extension: str


class ScreenshotValidator:
    """Domain servisi: yüklenen içeriğin geçerli bir ekran görüntüsü olup olmadığına karar verir.

    Boyut sınırı ayardan gelir (MAX_UPLOAD_SIZE_MB); kompozisyon kökünde bir kez
    oluşturulup ekran görüntüsü handler'ına enjekte edilir.
    """

    PNG = ImageType("image/png", "png")
    JPEG = ImageType("image/jpeg", "jpg")
    FILE_SIGNATURES: dict[bytes, ImageType] = {
        b"\x89PNG\r\n\x1a\n": PNG,
        b"\xff\xd8\xff": JPEG,
    }

    def __init__(self, max_size_bytes: int) -> None:
        self._max_size_bytes = max_size_bytes

    @property
    def max_size_bytes(self) -> int:
        return self._max_size_bytes

    def validate(self, content: bytes) -> ImageType:
        """İçerik geçerli bir ekran görüntüsüyse türünü döndürür, değilse InvalidFileError fırlatır."""
        if not content:
            raise InvalidFileError("Dosya boş.")
        if len(content) > self._max_size_bytes:
            max_mb = self._max_size_bytes / (1024 * 1024)
            raise InvalidFileError(f"Dosya boyutu en fazla {max_mb:g} MB olabilir.")
        for signature, image_type in self.FILE_SIGNATURES.items():
            if content.startswith(signature):
                return image_type
        raise InvalidFileError("Yalnızca PNG veya JPG formatında ekran görüntüsü yüklenebilir.")
