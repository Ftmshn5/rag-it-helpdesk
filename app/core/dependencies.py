"""Bağımlılık enjeksiyonu (Dependency Injection) — uygulamanın "composition root"u.

Hangi arayüzün hangi somut sınıfla karşılanacağına yalnızca burada karar verilir
(UnitOfWork → SqlAlchemyUnitOfWork, EventBus → InMemoryEventBus). API katmanı
ihtiyaç duyduğu şeyleri FastAPI `Depends` ile buradan alır; somut sınıfları
kendisi oluşturmaz. Testlerde bu fonksiyonlar `app.dependency_overrides` ile
sahteleriyle değiştirilebilir.
"""

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.application.interfaces.event_bus import EventBus
from app.application.interfaces.unit_of_work import UnitOfWork
from app.core.event_subscriptions import register_subscribers
from app.infrastructure.db.session import check_database_connection, get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus


def create_event_bus() -> EventBus:
    """Uygulama açılışında bir kez çağrılır; dinleyiciler burada kaydedilir."""
    event_bus = InMemoryEventBus()
    register_subscribers(event_bus)
    return event_bus


def get_event_bus(request: Request) -> EventBus:
    # Tüm istekler aynı bus'ı paylaşır: abonelikler uygulama ömrü boyunca geçerli
    return request.app.state.event_bus


def get_unit_of_work(event_bus: EventBus = Depends(get_event_bus)) -> UnitOfWork:
    # Her istek kendi Unit of Work'ünü (dolayısıyla kendi transaction'ını) alır
    return SqlAlchemyUnitOfWork(event_bus)


def get_db_session() -> Iterator[Session]:
    """Okuma tarafı (queries) için düz oturum; yazma işlemleri UnitOfWork kullanır."""
    yield from get_session()


def get_database_status() -> bool:
    return check_database_connection()
