"""Domain hataları.

Mesajlar doğrudan kullanıcıya gösterildiği için Türkçedir.
"""


class BusinessRuleViolation(Exception):
    """Bir iş kuralı ihlal edildi (örn. zimmetli cihaz tekrar zimmetlenemez)."""


class InvalidFileError(BusinessRuleViolation):
    """Yüklenen dosya kurallara uymuyor (tür veya boyut)."""
