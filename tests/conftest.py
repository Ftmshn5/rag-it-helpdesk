import pytest
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.session import check_database_connection, engine
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from tests.fakes import FakeEventBus, FakeUnitOfWork


@pytest.fixture
def db_connection():
    """Gerçek veritabanı bağlantısı; test bitince her şey geri alınır.

    Dış transaction en sonda rollback edilir. Unit of Work'ün commit'leri bu dış
    transaction içinde yalnızca bir SAVEPOINT'i kapatır, yani kalıcı olmaz.
    """
    if not check_database_connection():
        pytest.skip("Veritabanı çalışmıyor (docker compose up -d)")
    connection = engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture
def event_bus() -> FakeEventBus:
    return FakeEventBus()


@pytest.fixture
def sqlalchemy_uow(db_connection, event_bus) -> SqlAlchemyUnitOfWork:
    session_factory = sessionmaker(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    return SqlAlchemyUnitOfWork(event_bus, session_factory)


@pytest.fixture(params=["in_memory", "sqlalchemy"])
def uow(request, event_bus):
    """Aynı testi hem sahte hem gerçek Unit of Work ile çalıştırır."""
    if request.param == "in_memory":
        return FakeUnitOfWork(event_bus)
    return request.getfixturevalue("sqlalchemy_uow")
