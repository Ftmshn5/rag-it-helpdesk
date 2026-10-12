"""Cihaz endpoint testleri: HTTP durum kodları ve Türkçe hata mesajları.

Unit of Work sahtesiyle değiştirildiği için veritabanı gerekmez.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_unit_of_work
from app.domain.enums import DeviceStatus, UserRole
from app.domain.inventory import Device
from app.domain.user import User
from app.main import create_app
from tests.fakes import FakeUnitOfWork

ADMIN = {"X-User-Id": "1"}
USER = {"X-User-Id": "2"}

VALID_BODY = {
    "asset_tag": "PC-0100",
    "type": "Masaüstü",
    "brand": "Dell",
    "model": "OptiPlex",
    "serial_number": "SN-100",
}


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.users.add(User(full_name="Yönetici", email="admin@x.edu", role=UserRole.ADMIN))
    uow.users.add(User(full_name="Kullanıcı", email="user@x.edu", role=UserRole.USER))
    return uow


@pytest.fixture
def client(uow) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_unit_of_work] = lambda: uow
    return TestClient(app)


def test_register_device_returns_201_with_id(client):
    response = client.post("/devices", json=VALID_BODY, headers=ADMIN)

    assert response.status_code == 201
    assert response.json() == {"id": 1}


def test_missing_user_header_returns_401(client):
    response = client.post("/devices", json=VALID_BODY)

    assert response.status_code == 401
    assert response.json()["detail"] == "X-User-Id başlığı gerekli."


def test_non_admin_gets_403(client):
    response = client.post("/devices", json=VALID_BODY, headers=USER)

    assert response.status_code == 403
    assert response.json()["detail"] == "Bu işlem için yetkiniz yok."


def test_duplicate_asset_tag_returns_409(client):
    client.post("/devices", json=VALID_BODY, headers=ADMIN)
    response = client.post(
        "/devices", json=VALID_BODY | {"serial_number": "SN-OTHER"}, headers=ADMIN
    )

    assert response.status_code == 409
    assert "zaten kayıtlı" in response.json()["detail"]


def test_invalid_body_returns_422_with_turkish_summary(client):
    response = client.post("/devices", json=VALID_BODY | {"asset_tag": ""}, headers=ADMIN)

    assert response.status_code == 422
    body = response.json()
    assert body["detail"].startswith("Gönderilen veriler geçersiz")
    assert body["errors"][0]["field"] == "body.asset_tag"


def test_status_cannot_be_changed_via_update(client, uow):
    device = uow.devices.add(
        Device(asset_tag="PC-1", type="PC", brand="HP", model="X", serial_number="S1")
    )

    response = client.patch(
        f"/devices/{device.id}", json={"status": "RETIRED", "location": "Depo"}, headers=ADMIN
    )

    assert response.status_code == 204
    updated = uow.devices.get(device.id)
    assert updated.location == "Depo"
    assert updated.status == DeviceStatus.IN_STOCK  # status alanı yok sayıldı


def test_retire_unknown_device_returns_404(client):
    response = client.post("/devices/99/retire", headers=ADMIN)

    assert response.status_code == 404
    assert response.json()["detail"] == "Cihaz bulunamadı."


def test_retire_assigned_device_returns_409(client, uow):
    device = uow.devices.add(
        Device(
            asset_tag="PC-1",
            type="PC",
            brand="HP",
            model="X",
            serial_number="S1",
            status=DeviceStatus.ASSIGNED,
        )
    )

    response = client.post(f"/devices/{device.id}/retire", headers=ADMIN)

    assert response.status_code == 409
