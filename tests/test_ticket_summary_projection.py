"""ticket_summary read model'i ve projektör testleri (gerçek PostgreSQL)."""

from datetime import timedelta

import pytest

from app.application.commands.ai_answers import (
    AutoAnswerTicketHandler,
    EvaluateAiAnswer,
    EvaluateAiAnswerHandler,
)
from app.application.commands.ticket_workflow import (
    AddComment,
    AddCommentHandler,
    AssignTicket,
    AssignTicketHandler,
)
from app.application.commands.tickets import CreateTicket, CreateTicketHandler
from app.core.event_subscriptions import register_subscribers
from app.domain.enums import TicketCategory, TicketModifier, TicketStatus, UserRole
from app.domain.inventory import Device
from app.domain.ticket import Ticket
from app.domain.user import User
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.db.models import TicketModel
from app.infrastructure.db.projections import TicketSummaryProjector
from app.infrastructure.db.read_models import TicketSummaryModel
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from tests.fakes import FakeEventBus


@pytest.fixture
def projector(session_factory) -> TicketSummaryProjector:
    return TicketSummaryProjector(session_factory)


@pytest.fixture
def people(session_factory):
    uow = SqlAlchemyUnitOfWork(FakeEventBus(), session_factory)
    with uow:
        dean = uow.users.add(User(full_name="Prof. Dr. Dekan", email="rm.vip@test.edu", is_vip=True))
        tech = uow.users.add(
            User(full_name="Ali Teknisyen", email="rm.tech@test.edu", role=UserRole.TECHNICIAN)
        )
        admin = uow.users.add(User(full_name="Yönetici", email="rm.adm@test.edu", role=UserRole.ADMIN))
        device = uow.devices.add(
            Device(asset_tag="RM-0001", type="PC", brand="Dell", model="X", serial_number="RM-S1")
        )
        uow.commit()
    return dean, tech, admin, device


def read_row(session_factory, ticket_id) -> TicketSummaryModel | None:
    with session_factory() as session:
        return session.get(TicketSummaryModel, ticket_id)


def add_ticket(session_factory, **values) -> Ticket:
    uow = SqlAlchemyUnitOfWork(FakeEventBus(), session_factory)
    with uow:
        ticket = uow.tickets.add(Ticket(**values))
        uow.commit()
    return ticket


# --- Projektör ---


def test_refresh_builds_denormalized_row(session_factory, projector, people):
    dean, _, _, device = people
    ticket = add_ticket(
        session_factory,
        title="Projeksiyon yok",
        description="-",
        category=TicketCategory.HARDWARE,
        requester_id=dean.id,
        device_id=device.id,
        modifiers=[TicketModifier.VIP, TicketModifier.URGENT],
    )

    projector.refresh(ticket.id)

    row = read_row(session_factory, ticket.id)
    assert (row.requester_name, row.device_asset_tag) == ("Prof. Dr. Dekan", "RM-0001")
    assert (row.is_vip, row.is_urgent) == (True, True)
    # Decorator'dan gelen hesaplanmış alanlar
    assert (row.sla_hours, row.priority_score) == (4, 80)
    assert row.due_at == ticket.created_at + timedelta(hours=4)
    assert row.status == "OPEN"
    assert row.assignee_name is None


def test_refresh_reflects_later_changes(session_factory, projector, people):
    dean, tech, _, _ = people
    ticket = add_ticket(
        session_factory,
        title="t",
        description="-",
        category=TicketCategory.NETWORK,
        requester_id=dean.id,
        status=TicketStatus.ESCALATED,
    )
    projector.refresh(ticket.id)

    with session_factory() as session:
        model = session.get(TicketModel, ticket.id)
        model.status = TicketStatus.ASSIGNED
        model.assignee_id = tech.id
        session.commit()
    projector.refresh(ticket.id)

    row = read_row(session_factory, ticket.id)
    assert (row.status, row.assignee_name) == ("ASSIGNED", "Ali Teknisyen")


def test_refresh_is_idempotent(session_factory, projector, people):
    """Aynı olay iki kez işlense de satır aynı kalır (sıra ve tekrar önemsiz)."""
    dean, *_ = people
    ticket = add_ticket(
        session_factory, title="t", description="-", category=TicketCategory.ACCOUNT, requester_id=dean.id
    )

    projector.refresh(ticket.id)
    first = read_row(session_factory, ticket.id)
    projector.refresh(ticket.id)
    second = read_row(session_factory, ticket.id)

    assert (first.status, first.sla_hours, first.comment_count) == (
        second.status,
        second.sla_hours,
        second.comment_count,
    )


def test_refresh_removes_row_of_deleted_ticket(session_factory, projector, people):
    dean, *_ = people
    ticket = add_ticket(
        session_factory, title="t", description="-", category=TicketCategory.ACCOUNT, requester_id=dean.id
    )
    projector.refresh(ticket.id)

    with session_factory() as session:
        session.delete(session.get(TicketModel, ticket.id))
        session.commit()
    projector.refresh(ticket.id)

    assert read_row(session_factory, ticket.id) is None


def test_rebuild_covers_tickets_created_without_events(session_factory, projector, people):
    """Olay üretmeden eklenen kayıtlar (seed, eski veri) rebuild ile read model'e girer."""
    dean, *_ = people
    ticket = add_ticket(
        session_factory, title="t", description="-", category=TicketCategory.ACCOUNT, requester_id=dean.id
    )
    assert read_row(session_factory, ticket.id) is None

    projector.rebuild()

    assert read_row(session_factory, ticket.id).requester_name == "Prof. Dr. Dekan"


# --- Olaylarla güncelleme (Observer) ---


def test_read_model_follows_write_side_through_events(session_factory, projector, people):
    dean, tech, admin, _ = people
    bus = InMemoryEventBus()
    register_subscribers(
        bus,
        make_auto_answer_handler=lambda: AutoAnswerTicketHandler(
            SqlAlchemyUnitOfWork(bus, session_factory), FakeAiSupport(), 0.6
        ),
        ticket_summary_projector=projector,
    )
    uow = SqlAlchemyUnitOfWork(bus, session_factory)

    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicket(
            actor_id=dean.id, title="Şifremi unuttum", description="-", category=TicketCategory.ACCOUNT
        )
    )
    row = read_row(session_factory, ticket_id)
    assert (row.status, row.ai_confidence, row.sla_hours) == ("AI_ANSWERED", 0.85, 24)

    EvaluateAiAnswerHandler(uow).handle(
        EvaluateAiAnswer(actor_id=dean.id, ticket_id=ticket_id, is_helpful=False)
    )
    AssignTicketHandler(uow).handle(
        AssignTicket(actor_id=admin.id, ticket_id=ticket_id, technician_id=tech.id)
    )
    AddCommentHandler(uow).handle(
        AddComment(actor_id=tech.id, ticket_id=ticket_id, content="Hesap kilidi açıldı.")
    )

    row = read_row(session_factory, ticket_id)
    assert row.status == "ASSIGNED"
    assert row.ai_feedback == "NOT_HELPFUL"
    assert row.assignee_name == "Ali Teknisyen"
    assert row.comment_count == 1
