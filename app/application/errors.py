"""Application katmanı hataları (iş kuralı değil, akış/erişim hataları).

API katmanı bunları uygun HTTP durum kodlarına çevirir. Mesajlar Türkçedir.
"""


class AuthenticationError(Exception):
    """İşlemi yapan kullanıcı belirlenemedi (X-User-Id yok veya geçersiz)."""


class PermissionDeniedError(Exception):
    """Kullanıcının rolü bu işlem için yetkili değil."""


class NotFoundError(Exception):
    """İstenen kayıt bulunamadı."""
