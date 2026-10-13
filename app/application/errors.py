"""Application katmanı hataları (iş kuralı değil, akış/erişim hataları).

İş kuralı ihlalleri domain/errors.py'deki DomainError hiyerarşisindedir; buradakiler
"kim, neye erişebilir, kayıt var mı" sorularının hatalarıdır. Hepsi ApplicationError'dan
türer. API katmanı bunları uygun HTTP durum kodlarına çevirir. Mesajlar Türkçedir.
"""


class ApplicationError(Exception):
    """Application katmanı hatalarının ortak tabanı."""


class AuthenticationError(ApplicationError):
    """İşlemi yapan kullanıcı belirlenemedi (X-User-Id yok veya geçersiz)."""


class PermissionDeniedError(ApplicationError):
    """Kullanıcının rolü bu işlem için yetkili değil."""


class NotFoundError(ApplicationError):
    """İstenen kayıt bulunamadı."""
