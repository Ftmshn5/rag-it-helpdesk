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
    mime_type: str
    extension: str


PNG = ImageType("image/png", "png")
JPEG = ImageType("image/jpeg", "jpg")

FILE_SIGNATURES: dict[bytes, ImageType] = {
    b"\x89PNG\r\n\x1a\n": PNG,
    b"\xff\xd8\xff": JPEG,
}


def validate_screenshot(content: bytes, max_size_bytes: int) -> ImageType:
    """İçerik geçerli bir ekran görüntüsüyse türünü döndürür, değilse hata fırlatır."""
    if not content:
        raise InvalidFileError("Dosya boş.")
    if len(content) > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise InvalidFileError(f"Dosya boyutu en fazla {max_mb:g} MB olabilir.")
    for signature, image_type in FILE_SIGNATURES.items():
        if content.startswith(signature):
            return image_type
    raise InvalidFileError("Yalnızca PNG veya JPG formatında ekran görüntüsü yüklenebilir.")
