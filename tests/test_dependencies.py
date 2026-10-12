"""Bağımlılık enjeksiyonu testleri.

Geçici bir endpoint üzerinden, FastAPI'nin endpoint'lere ne enjekte ettiğini kontrol eder.
"""

from fastapi import Depends
from fastapi.testclient import TestClient

from app.application.interfaces.unit_of_work import UnitOfWork
from app.core.dependencies import get_unit_of_work
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import create_app
from tests.fakes import FakeUnitOfWork


def make_app_with_probe():
    app = create_app()
    received: list[UnitOfWork] = []

    @app.get("/_probe")
    def probe(uow: UnitOfWork = Depends(get_unit_of_work)):
        received.append(uow)
        return {}

    return app, received


def test_endpoint_receives_sqlalchemy_unit_of_work_with_app_event_bus():
    app, received = make_app_with_probe()
    client = TestClient(app)

    client.get("/_probe")
    client.get("/_probe")

    first, second = received
    assert isinstance(first, SqlAlchemyUnitOfWork)
    # Her istek yeni bir Unit of Work alır...
    assert first is not second
    # ...ama hepsi uygulamanın tek event bus'ını paylaşır
    assert first.event_bus is app.state.event_bus
    assert second.event_bus is app.state.event_bus


def test_unit_of_work_can_be_replaced_with_fake():
    app, received = make_app_with_probe()
    fake = FakeUnitOfWork()
    app.dependency_overrides[get_unit_of_work] = lambda: fake

    TestClient(app).get("/_probe")

    assert received == [fake]
