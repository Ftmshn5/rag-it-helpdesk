"""Zaman kaynağı."""

from datetime import UTC, datetime


class Clock:
    """Tüm zaman damgaları saat dilimi bilgisiyle (UTC) tek bir yerden üretilir."""

    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)
