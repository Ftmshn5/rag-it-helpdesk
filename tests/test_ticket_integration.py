"""Ticket akışının gerçek PostgreSQL üzerinde testi.

Veritabanında yalnızca modifiers listesi durur; okurken Factory bu listeden
decorator'lı nesneyi yeniden kurar. Bu test o döngüyü uçtan uca doğrular.
"""

from app.application.commands.attachments import AttachScreenshotCommand, AttachScreenshotHandler
from app.application.commands.ticket_workflow import (
    AddCommentCommand,
    AddCommentHandler,
    AssignTicketCommand,
    AssignTicketHandler,
    CloseTicketCommand,
    CloseTicketHandler,
    ReopenTicketCommand,
    ReopenTicketHandler,
    ResolveTicketCommand,
    ResolveTicketHandler,
    StartWorkCommand,
    StartWorkHandler,
)
from app.application.commands.tickets import (
    CreateTicketCommand,
    CreateTicketHandler,
    SetTicketUrgencyCommand,
    SetTicketUrgencyHandler,
)
from app.domain.enums import TicketCategory, TicketModifier, TicketStatus, UserRole
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
        CreateTicketCommand(
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
        SetTicketUrgencyCommand(actor_id=admin.id, ticket_id=ticket_id, is_urgent=True)
    )
    with uow:
        ticket = uow.tickets.get(ticket_id)
        behavior = TicketBehaviorFactory.create(ticket)

    assert ticket.modifiers == [TicketModifier.VIP, TicketModifier.URGENT]
    assert isinstance(behavior, UrgentTicket)
    assert (behavior.sla_hours(), behavior.priority_score()) == (4, 80)


def test_full_lifecycle_with_reopen_on_real_database(sqlalchemy_uow):
    """Teknisyen çözer → kullanıcı yeniden açar → başka teknisyene atanır → kapanır."""
    uow = sqlalchemy_uow
    with uow:
        user = uow.users.add(User(full_name="A", email="it.req@test.edu"))
        admin = uow.users.add(User(full_name="Y", email="it.adm2@test.edu", role=UserRole.ADMIN))
        ali = uow.users.add(User(full_name="T1", email="it.t1@test.edu", role=UserRole.TECHNICIAN))
        elif_ = uow.users.add(User(full_name="T2", email="it.t2@test.edu", role=UserRole.TECHNICIAN))
        uow.commit()
    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicketCommand(actor_id=user.id, title="VPN", description="d", category=TicketCategory.NETWORK)
    )
    with uow:  # AI adımı 7. adımda; şimdilik eskalasyonu doğrudan domain ile yapıyoruz
        ticket = uow.tickets.get(ticket_id)
        ticket.escalate()
        uow.tickets.update(ticket)
        uow.commit()

    AssignTicketHandler(uow).handle(
        AssignTicketCommand(actor_id=admin.id, ticket_id=ticket_id, technician_id=ali.id)
    )
    StartWorkHandler(uow).handle(StartWorkCommand(actor_id=ali.id, ticket_id=ticket_id))
    AddCommentHandler(uow).handle(
        AddCommentCommand(actor_id=ali.id, ticket_id=ticket_id, content="Sertifika yenilendi.")
    )
    ResolveTicketHandler(uow).handle(ResolveTicketCommand(actor_id=ali.id, ticket_id=ticket_id))
    ReopenTicketHandler(uow).handle(ReopenTicketCommand(actor_id=user.id, ticket_id=ticket_id))
    AssignTicketHandler(uow).handle(
        AssignTicketCommand(actor_id=admin.id, ticket_id=ticket_id, technician_id=elif_.id)
    )
    StartWorkHandler(uow).handle(StartWorkCommand(actor_id=elif_.id, ticket_id=ticket_id))
    ResolveTicketHandler(uow).handle(ResolveTicketCommand(actor_id=elif_.id, ticket_id=ticket_id))
    CloseTicketHandler(uow).handle(CloseTicketCommand(actor_id=user.id, ticket_id=ticket_id))

    with uow:
        ticket = uow.tickets.get(ticket_id)
    assert ticket.status == TicketStatus.CLOSED
    assert ticket.assignee_id == elif_.id
    assert ticket.resolved_at is not None
    published = [e.new_status for e in uow.event_bus.published if hasattr(e, "new_status")]
    assert published == [
        TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.ESCALATED,
        TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    ]


def test_screenshot_is_stored_on_disk_and_recorded_in_database(sqlalchemy_uow, tmp_path):
    uow = sqlalchemy_uow
    with uow:
        user = uow.users.add(User(full_name="A", email="it.att@test.edu"))
        uow.commit()
    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicketCommand(
            actor_id=user.id, title="Mavi ekran", description="d", category=TicketCategory.SOFTWARE
        )
    )
    png = b"\x89PNG\r\n\x1a\n" + b"\x01" * 50

    attachment_id = AttachScreenshotHandler(uow, LocalFileStorage(tmp_path), 1024).handle(
        AttachScreenshotCommand(actor_id=user.id, ticket_id=ticket_id, content=png)
    )

    with uow:
        attachment = uow.ticket_attachments.get(attachment_id)
    assert attachment.ticket_id == ticket_id
    assert attachment.mime_type == "image/png"
    assert (tmp_path / attachment.file_path).read_bytes() == png
