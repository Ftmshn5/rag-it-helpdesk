import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_unit_of_work
from app.domain.enums import TicketModifier, UserRole
from app.domain.user import User
from app.main import create_app
from tests.fakes import FakeUnitOfWork

USER, VIP, ADMIN = {"X-User-Id": "1"}, {"X-User-Id": "2"}, {"X-User-Id": "3"}
BODY = {"title": "Yazıcı çalışmıyor", "description": "Kağıt sıkışıyor", "category": "HARDWARE"}


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.users.add(User(full_name="Ayşe", email="ayse@x.edu"))
    uow.users.add(User(full_name="Dekan", email="dekan@x.edu", is_vip=True))
    uow.users.add(User(full_name="Yönetici", email="admin@x.edu", role=UserRole.ADMIN))
    return uow


@pytest.fixture
def client(uow) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_unit_of_work] = lambda: uow
    return TestClient(app)


def test_create_ticket_returns_201(client, uow):
    response = client.post("/tickets", json=BODY | {"is_urgent": True}, headers=VIP)

    assert response.status_code == 201
    ticket = uow.tickets.get(response.json()["id"])
    assert ticket.modifiers == [TicketModifier.VIP, TicketModifier.URGENT]


def test_client_cannot_set_modifiers_directly(client, uow):
    """VIP istemciden gelmez; gönderilse bile yok sayılır."""
    response = client.post("/tickets", json=BODY | {"modifiers": ["VIP"]}, headers=USER)

    assert uow.tickets.get(response.json()["id"]).modifiers == []


def test_invalid_category_returns_422(client):
    response = client.post("/tickets", json=BODY | {"category": "PRINTER"}, headers=USER)

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "body.category"


def test_set_urgency_by_admin_returns_204(client, uow):
    ticket_id = client.post("/tickets", json=BODY, headers=USER).json()["id"]

    response = client.put(f"/tickets/{ticket_id}/urgency", json={"is_urgent": True}, headers=ADMIN)

    assert response.status_code == 204
    assert uow.tickets.get(ticket_id).is_urgent


def test_set_urgency_by_user_returns_403(client):
    ticket_id = client.post("/tickets", json=BODY, headers=USER).json()["id"]

    response = client.put(f"/tickets/{ticket_id}/urgency", json={"is_urgent": True}, headers=USER)

    assert response.status_code == 403
