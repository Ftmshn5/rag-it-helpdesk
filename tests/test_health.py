"""/health endpoint testleri.

Gerçek veritabanına ihtiyaç duymazlar: DB durumu bağımlılığı sahte değerle değiştirilir.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_database_status
from app.main import app


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_returns_ok_when_database_is_up(client):
    app.dependency_overrides[get_database_status] = lambda: True

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_returns_503_when_database_is_down(client):
    app.dependency_overrides[get_database_status] = lambda: False

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["database"] == "unavailable"
