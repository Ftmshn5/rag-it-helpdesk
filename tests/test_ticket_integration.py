"""Ticket akışının gerçek PostgreSQL üzerinde testi.

Veritabanında yalnızca modifiers listesi durur; okurken Factory bu listeden
decorator'lı nesneyi yeniden kurar. Bu test o döngüyü uçtan uca doğrular.
"""

from app.application.commands.attachments import AttachScreenshot, AttachScreenshotHandler
from app.application.commands.tickets import (
    CreateTicket,
    CreateTicketHandler,
    SetTicketUrgency,
    SetTicketUrgencyHandler,
)
from app.domain.enums import TicketCategory, TicketModifier, UserRole
from app.domain.ticket_behavior import TicketBehaviorFactory, UrgentTicket
from app.domain.user import User
from app.infrastructure.storage.local_file_storage import LocalFileStorage


def test_modifiers_round_trip_and_factory_rebuilds_behavior(sqlalchemy_uow):
    uow = sqlalchemy_uow
    with uow:
        vip = uow.users.add(User(full_name="D", email="it.vip@test.edu", is_vip=True))
        admin = uow.users.add(User(full_name="Y", email="it.adm@test.edu", role=UserRole.ADMIN))
        uow.commit()

    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicket(
            actor_id=vip.id,
            title="Projeksiyon açılmıyor",
            description="Amfi 1",
            category=TicketCategory.HARDWARE,
        )
    )
    with uow:
        behavior = TicketBehaviorFactory.create(uow.tickets.get(ticket_id))
    assert behavior.sla_hours() == 24

    SetTicketUrgencyHandler(uow).handle(
        SetTicketUrgency(actor_id=admin.id, ticket_id=ticket_id, is_urgent=True)
    )
    with uow:
        ticket = uow.tickets.get(ticket_id)
        behavior = TicketBehaviorFactory.create(ticket)

    assert ticket.modifiers == [TicketModifier.VIP, TicketModifier.URGENT]
    assert isinstance(behavior, UrgentTicket)
    assert (behavior.sla_hours(), behavior.priority_score()) == (4, 80)


def test_screenshot_is_stored_on_disk_and_recorded_in_database(sqlalchemy_uow, tmp_path):
    uow = sqlalchemy_uow
    with uow:
        user = uow.users.add(User(full_name="A", email="it.att@test.edu"))
        uow.commit()
    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicket(
            actor_id=user.id, title="Mavi ekran", description="d", category=TicketCategory.SOFTWARE
        )
    )
    png = b"\x89PNG\r\n\x1a\n" + b"\x01" * 50

    attachment_id = AttachScreenshotHandler(uow, LocalFileStorage(tmp_path), 1024).handle(
        AttachScreenshot(actor_id=user.id, ticket_id=ticket_id, content=png)
    )

    with uow:
        attachment = uow.ticket_attachments.get(attachment_id)
    assert attachment.ticket_id == ticket_id
    assert attachment.mime_type == "image/png"
    assert (tmp_path / attachment.file_path).read_bytes() == png
