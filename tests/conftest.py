import os

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.dependencies import get_database
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import FakeEventBus, FakeUnitOfWork


@pytest.fixture
def db_connection():
    """Gerçek veritabanı bağlantısı; test bitince her şey geri alınır.

    Dış transaction en sonda rollback edilir. Unit of Work'ün commit'leri bu dış
    transaction içinde yalnızca bir SAVEPOINT'i kapatır, yani kalıcı olmaz.
    """
    database = get_database()
    if not database.is_available():
        # CI'da veritabanı testlerinin sessizce atlanıp "yeşil" görünmesini önler
        if os.environ.get("REQUIRE_DATABASE") == "1":
            pytest.fail("REQUIRE_DATABASE=1 ama veritabanına bağlanılamadı.")
        pytest.skip("Veritabanı çalışmıyor (docker compose up -d)")
    connection = database.engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture
def event_bus() -> FakeEventBus:
    return FakeEventBus()


@pytest.fixture
def session_factory(db_connection):
    """Test transaction'ına bağlı oturum fabrikası (commit'ler SAVEPOINT olur)."""
    return sessionmaker(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )


@pytest.fixture
def sqlalchemy_uow(session_factory, event_bus) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(event_bus, session_factory)


@pytest.fixture(params=["in_memory", "sqlalchemy"])
def uow(request, event_bus):
    """Aynı testi hem sahte hem gerçek Unit of Work ile çalıştırır."""
    if request.param == "in_memory":
        return FakeUnitOfWork(event_bus)
    return request.getfixturevalue("sqlalchemy_uow")
