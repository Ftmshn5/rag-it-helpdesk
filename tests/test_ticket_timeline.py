"""Talep zaman çizelgesi (E3) testleri (gerçek PostgreSQL).

read.ticket_timeline olaylardan beslenir (Observer): her yayınlanan talep olayı bir
satır ekler. Yeniden kurma geçmişi silmez, yalnızca eksik talepleri doldurur.
"""

import pytest

from app.application.commands.ai_answers import (
    AutoAnswerTicketHandler,
    EvaluateAiAnswerCommand,
    EvaluateAiAnswerHandler,
)
from app.application.commands.ticket_workflow import (
    AddCommentCommand,
    AddCommentHandler,
    AssignTicketCommand,
    AssignTicketHandler,
    StartWorkCommand,
    StartWorkHandler,
)
from app.application.commands.tickets import (
    CreateTicketCommand,
    CreateTicketHandler,
    SetTicketUrgencyCommand,
    SetTicketUrgencyHandler,
)
from app.application.queries.tickets import GetTicketDetailHandler, GetTicketDetailQuery, TimelineEntryKind
from app.domain.enums import TicketCategory, UserRole
from app.domain.ticket import Ticket, TicketComment
from app.domain.user import User
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.db.projections import TicketSummaryProjector, TicketTimelineProjector
from app.infrastructure.db.queries import SqlTicketQueries, SqlUserQueries
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from tests.fakes import FakeEventBus, subscribe_all

K = TimelineEntryKind


@pytest.fixture
def people(session_factory):
    uow = SqlAlchemyUnitOfWork(FakeEventBus(), session_factory)
    with uow:
        dean = uow.users.add(User(full_name="Zaman Dekan", email="tl.vip@test.edu", is_vip=True))
        tech = uow.users.add(User(full_name="Zaman Teknisyen", email="tl.tech@test.edu", role=UserRole.TECHNICIAN))
        admin = uow.users.add(User(full_name="Zaman Yönetici", email="tl.adm@test.edu", role=UserRole.ADMIN))
        uow.commit()
    return dean, tech, admin


def timeline_of(session_factory, ticket_id: int, actor_id: int):
    with session_factory() as session:
        handler = GetTicketDetailHandler(SqlTicketQueries(session), SqlUserQueries(session), ai_threshold=0.6)
        return handler.handle(GetTicketDetailQuery(actor_id=actor_id, ticket_id=ticket_id)).timeline


def test_timeline_is_fed_by_published_events(session_factory, people):
    dean, tech, admin = people
    bus = InMemoryEventBus()
    subscribe_all(
        bus,
        lambda: AutoAnswerTicketHandler(SqlAlchemyUnitOfWork(bus, session_factory), FakeAiSupport(), 0.6),
        projectors=(TicketSummaryProjector(session_factory), TicketTimelineProjector(session_factory)),
    )
    uow = SqlAlchemyUnitOfWork(bus, session_factory)

    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicketCommand(actor_id=dean.id, title="Şifremi unuttum", description="-", category=TicketCategory.ACCOUNT)
    )  # FakeAiSupport yanıtlar (güven 0.85) → OPEN → AI_ANSWERED
    EvaluateAiAnswerHandler(uow).handle(EvaluateAiAnswerCommand(actor_id=dean.id, ticket_id=ticket_id, is_helpful=False))
    AssignTicketHandler(uow).handle(AssignTicketCommand(actor_id=admin.id, ticket_id=ticket_id, technician_id=tech.id))
    StartWorkHandler(uow).handle(StartWorkCommand(actor_id=tech.id, ticket_id=ticket_id))
    AddCommentHandler(uow).handle(AddCommentCommand(actor_id=tech.id, ticket_id=ticket_id, content="Hesap açıldı."))
    SetTicketUrgencyHandler(uow).handle(SetTicketUrgencyCommand(actor_id=admin.id, ticket_id=ticket_id, is_urgent=True))

    timeline = timeline_of(session_factory, ticket_id, admin.id)

    assert [(entry.kind, entry.actor_name) for entry in timeline] == [
        (K.CREATED, "Zaman Dekan"),
        (K.AI_ANSWERED, None),  # sistem; AI'ın durum geçişi ayrıca yazılmaz (tekrar olmasın)
        (K.AI_FEEDBACK, "Zaman Dekan"),
        (K.STATUS_CHANGED, "Zaman Dekan"),  # çözülmedi → eskalasyon
        (K.STATUS_CHANGED, "Zaman Yönetici"),  # atama
        (K.STATUS_CHANGED, "Zaman Teknisyen"),  # çalışmaya başlandı
        (K.COMMENT, "Zaman Teknisyen"),
        (K.URGENCY, "Zaman Yönetici"),
    ]
    assert timeline[1].details == {"confidence": 0.85, "escalated": False}
    assert timeline[2].details == {"is_helpful": False}
    assert timeline[4].details["new_status"] == "ASSIGNED"
    assert timeline[4].details["assignee_name"] == "Zaman Teknisyen"
    assert timeline[6].details == {"excerpt": "Hesap açıldı."}
    assert timeline[7].details == {"is_urgent": True, "sla_hours": 4}
    assert [entry.occurred_at for entry in timeline] == sorted(entry.occurred_at for entry in timeline)

    # İş kuralı 4'ün okuma tarafı: AI güven skoru talep sahibine gösterilmez
    requester_view = timeline_of(session_factory, ticket_id, dean.id)
    assert "confidence" not in requester_view[1].details


def test_rebuild_backfills_missing_tickets_without_deleting_history(session_factory, people):
    dean, tech, _ = people
    uow = SqlAlchemyUnitOfWork(FakeEventBus(), session_factory)  # olay yayınlanmaz: çizelge boş
    with uow:
        ticket = uow.tickets.add(
            Ticket(title="Seed talebi", description="-", category=TicketCategory.HARDWARE, requester_id=dean.id)
        )
        uow.ticket_comments.add(TicketComment(ticket_id=ticket.id, author_id=tech.id, content="Bakıldı."))
        uow.commit()
    projector = TicketTimelineProjector(session_factory)

    assert projector.rebuild() >= 1
    with session_factory() as session:
        rows = projector.read_model.__table__
        kinds = [
            kind
            for (kind,) in session.execute(
                rows.select().with_only_columns(rows.c.kind).where(rows.c.ticket_id == ticket.id).order_by(rows.c.id)
            )
        ]
    assert kinds == ["CREATED", "COMMENT"]

    # İkinci kez çalıştırmak tekrar eklemez, mevcut geçmişe dokunmaz
    assert projector.rebuild() == 0
