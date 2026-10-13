"""GET /devices (teknisyen/yönetici) ve ekran görüntüsünü açma (gerçek PostgreSQL)."""

import pytest
from fastapi.testclient import TestClient

from app.application.commands.attachments import AttachScreenshotCommand, AttachScreenshotHandler
from app.application.commands.tickets import CreateTicketCommand, CreateTicketHandler
from app.core.dependencies import get_db_session, get_file_storage
from app.domain.attachments import ScreenshotValidator
from app.domain.enums import TicketCategory, UserRole
from app.domain.user import User
from app.infrastructure.db.projections import DeviceInventoryProjector
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.storage.local_file_storage import LocalFileStorage
from app.main import create_app
from tests.fakes import FakeEventBus

PNG = b"\x89PNG\r\n\x1a\n" + b"\x07" * 40


@pytest.fixture
def env(session_factory, tmp_path):
    uow = SqlAlchemyUnitOfWork(FakeEventBus(), session_factory)
    with uow:
        requester = uow.users.add(User(full_name="Talep Sahibi", email="tq.req@test.edu"))
        stranger = uow.users.add(User(full_name="Başkası", email="tq.other@test.edu"))
        tech = uow.users.add(
            User(full_name="Teknisyen", email="tq.tech@test.edu", role=UserRole.TECHNICIAN)
        )
        uow.commit()
    storage = LocalFileStorage(tmp_path)

    app = create_app()

    def test_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = test_session
    app.dependency_overrides[get_file_storage] = lambda: storage
    return uow, storage, TestClient(app), requester, stranger, tech


def headers(user) -> dict:
    return {"X-User-Id": str(user.id)}


def create_ticket_with_screenshot(uow, storage, requester) -> tuple[int, int]:
    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicketCommand(
            actor_id=requester.id, title="Mavi ekran", description="-", category=TicketCategory.SOFTWARE
        )
    )
    attachment_id = AttachScreenshotHandler(uow, storage, ScreenshotValidator(1024)).handle(
        AttachScreenshotCommand(actor_id=requester.id, ticket_id=ticket_id, content=PNG)
    )
    return ticket_id, attachment_id


# --- Cihaz listesi ---


def test_device_list_is_for_technicians_and_admins(session_factory, env):
    *_, client, requester, _, tech = env
    DeviceInventoryProjector(session_factory).rebuild()

    response = client.get("/devices", headers=headers(tech))
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    assert client.get("/devices", headers=headers(requester)).status_code == 403


# --- Ekran görüntüsünü açma ---


def test_requester_can_open_screenshot(env):
    uow, storage, client, requester, *_ = env
    ticket_id, attachment_id = create_ticket_with_screenshot(uow, storage, requester)

    response = client.get(f"/tickets/{ticket_id}/attachments/{attachment_id}", headers=headers(requester))

    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_other_users_cannot_open_screenshot(env):
    uow, storage, client, requester, stranger, tech = env
    ticket_id, attachment_id = create_ticket_with_screenshot(uow, storage, requester)
    path = f"/tickets/{ticket_id}/attachments/{attachment_id}"

    assert client.get(path, headers=headers(stranger)).status_code == 403
    # Atanmamış teknisyen de göremez (talebin tarafı değil)
    assert client.get(path, headers=headers(tech)).status_code == 403


def test_attachment_cannot_be_opened_through_another_ticket(env):
    """Ek numarası tahmin edilerek, erişimi olunan başka bir talebin adresiyle açılamaz."""
    uow, storage, client, requester, stranger, _ = env
    _, secret_attachment = create_ticket_with_screenshot(uow, storage, requester)
    own_ticket = CreateTicketHandler(uow).handle(
        CreateTicketCommand(actor_id=stranger.id, title="Benim talebim", description="-", category=TicketCategory.ACCOUNT)
    )

    response = client.get(
        f"/tickets/{own_ticket}/attachments/{secret_attachment}", headers=headers(stranger)
    )

    assert response.status_code == 404
