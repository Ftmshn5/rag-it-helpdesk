"""Ekran görüntüsü command handler testleri."""

import pytest

from app.application.commands.attachments import AttachScreenshot, AttachScreenshotHandler
from app.application.errors import PermissionDeniedError
from app.domain.enums import TicketCategory, TicketStatus, UserRole
from app.domain.errors import BusinessRuleViolation, InvalidFileError
from app.domain.events import ScreenshotAttached
from app.domain.ticket import Ticket
from app.domain.user import User
from tests.fakes import FakeUnitOfWork, InMemoryFileStorage

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
LIMIT = 1024
REQUESTER_ID, TECHNICIAN_ID, ADMIN_ID, STRANGER_ID = 1, 2, 3, 4


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.users.add(User(full_name="Ayşe", email="a@x.edu"))
    uow.users.add(User(full_name="Ali", email="t@x.edu", role=UserRole.TECHNICIAN))
    uow.users.add(User(full_name="Can", email="c@x.edu", role=UserRole.ADMIN))
    uow.users.add(User(full_name="Mehmet", email="m@x.edu"))
    uow.tickets.add(
        Ticket(
            title="Ekran mavi",
            description="Açılışta hata",
            category=TicketCategory.SOFTWARE,
            requester_id=REQUESTER_ID,
            assignee_id=TECHNICIAN_ID,
        )
    )
    return uow


@pytest.fixture
def storage() -> InMemoryFileStorage:
    return InMemoryFileStorage()


def attach(uow, storage, actor_id=REQUESTER_ID, content=PNG_BYTES) -> int:
    return AttachScreenshotHandler(uow, storage, LIMIT).handle(
        AttachScreenshot(actor_id=actor_id, ticket_id=1, content=content)
    )


@pytest.mark.parametrize("actor_id", [REQUESTER_ID, TECHNICIAN_ID, ADMIN_ID])
def test_allowed_users_can_attach_png(uow, storage, actor_id):
    attachment_id = attach(uow, storage, actor_id=actor_id)

    attachment = uow.ticket_attachments.get(attachment_id)
    assert attachment.mime_type == "image/png"
    assert attachment.file_path.startswith("tickets/1/")
    assert storage.files[attachment.file_path] == PNG_BYTES
    [event] = uow.event_bus.published
    assert isinstance(event, ScreenshotAttached)
    assert event.uploaded_by == actor_id


def test_other_users_cannot_attach_and_no_file_is_written(uow, storage):
    with pytest.raises(PermissionDeniedError, match="ek yükleme yetkiniz yok"):
        attach(uow, storage, actor_id=STRANGER_ID)
    assert storage.files == {}


def test_invalid_file_is_rejected_before_writing(uow, storage):
    with pytest.raises(InvalidFileError):
        attach(uow, storage, content=b"GIF89a....")
    assert storage.files == {}
    assert uow.ticket_attachments.items == {}


def test_closed_ticket_rejects_attachment(uow, storage):
    ticket = uow.tickets.get(1)
    ticket.status = TicketStatus.CLOSED
    uow.tickets.update(ticket)

    with pytest.raises(BusinessRuleViolation, match="Kapanmış talebe"):
        attach(uow, storage)
    assert storage.files == {}


def test_file_is_deleted_if_database_commit_fails(uow, storage, monkeypatch):
    """Telafi edici işlem: DB kaydı olmazsa diskte yetim dosya kalmamalı."""

    def failing_commit():
        raise RuntimeError("veritabanı bağlantısı koptu")

    monkeypatch.setattr(uow, "_commit", failing_commit)

    with pytest.raises(RuntimeError, match="bağlantısı koptu"):
        attach(uow, storage)

    assert storage.files == {}
    assert uow.event_bus.published == []
