from datetime import UTC, datetime


def utc_now() -> datetime:
    """Tüm zaman damgaları saat dilimi bilgisiyle (UTC) üretilir."""
    return datetime.now(UTC)
