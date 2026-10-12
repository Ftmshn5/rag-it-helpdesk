"""Domain hataları.

Mesajlar doğrudan kullanıcıya gösterildiği için Türkçedir.
"""


class BusinessRuleViolation(Exception):
    """Bir iş kuralı ihlal edildi (örn. zimmetli cihaz tekrar zimmetlenemez)."""
