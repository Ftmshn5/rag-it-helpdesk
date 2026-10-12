"""Bağımlılık enjeksiyonu (Dependency Injection) noktası.

API katmanı somut altyapı sınıflarını doğrudan oluşturmaz; ihtiyaç duyduğu şeyleri
buradaki fonksiyonlardan FastAPI `Depends` ile alır. Testlerde bu fonksiyonlar
`app.dependency_overrides` ile sahteleriyle değiştirilebilir.
"""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.infrastructure.db.session import check_database_connection, get_session


def get_db_session() -> Iterator[Session]:
    yield from get_session()


def get_database_status() -> bool:
    return check_database_connection()
