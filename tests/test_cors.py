"""CORS: frontend'in adresi izinli, başka siteler değil."""

from fastapi.testclient import TestClient

from app.main import create_app


def preflight(origin: str):
    """Tarayıcının asıl istekten önce gönderdiği izin sorusu (OPTIONS)."""
    return TestClient(create_app()).options(
        "/tickets/mine",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-User-Id",
        },
    )


def test_frontend_origin_is_allowed_with_user_header():
    response = preflight("http://localhost:5173")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-user-id" in response.headers["access-control-allow-headers"].lower()


def test_other_origins_are_not_allowed():
    response = preflight("https://kotu-site.example")

    assert "access-control-allow-origin" not in response.headers
