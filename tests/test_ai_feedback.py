"""UC-02 (AI önerisini değerlendir) testleri ve ana akışın uçtan uca testi."""

import pytest
from fastapi.testclient import TestClient

from app.application.commands.ai_answers import (
    AutoAnswerTicketHandler,
    EvaluateAiAnswer,
    EvaluateAiAnswerHandler,
)
from app.application.commands.ticket_workflow import (
    AssignTicket,
    AssignTicketHandler,
    CloseTicket,
    CloseTicketHandler,
    ResolveTicket,
    ResolveTicketHandler,
    StartWork,
    StartWorkHandler,
)
from app.application.commands.tickets import CreateTicket, CreateTicketHandler
from app.application.errors import NotFoundError, PermissionDeniedError
from app.core.dependencies import get_unit_of_work
from app.core.event_subscriptions import register_subscribers
from app.domain.enums import AiFeedback, TicketCategory, TicketStatus, UserRole
from app.domain.errors import DomainError
from app.domain.events import AiFeedbackGiven, TicketStatusChanged
from app.domain.ticket import AIResponse, Ticket
from app.domain.user import User
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from app.main import create_app
from tests.fakes import FakeUnitOfWork

S = TicketStatus
REQUESTER, OTHER_USER, ADMIN = 1, 2, 3


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.users.add(User(full_name="Ayşe", email="ayse@x.edu"))
    uow.users.add(User(full_name="Mehmet", email="mehmet@x.edu"))
    uow.users.add(User(full_name="Can", email="can@x.edu", role=UserRole.ADMIN))
    return uow


def add_answered_ticket(uow, status=S.AI_ANSWERED, with_response=True) -> int:
    ticket = uow.tickets.add(
        Ticket(
            title="Şifremi unuttum",
            description="-",
            category=TicketCategory.ACCOUNT,
            requester_id=REQUESTER,
            status=status,
        )
    )
    if with_response:
        uow.ai_responses.add(AIResponse(ticket_id=ticket.id, answer="Sıfırlayın.", confidence=0.85))
    return ticket.id


def evaluate(uow, ticket_id, is_helpful, actor_id=REQUESTER) -> None:
    EvaluateAiAnswerHandler(uow).handle(
        EvaluateAiAnswer(actor_id=actor_id, ticket_id=ticket_id, is_helpful=is_helpful)
    )


def test_helpful_answer_closes_ticket(uow):
    ticket_id = add_answered_ticket(uow)

    evaluate(uow, ticket_id, is_helpful=True)

    ticket = uow.tickets.get(ticket_id)
    assert ticket.status == S.CLOSED
    assert ticket.resolved_at is not None
    assert uow.ai_responses.get_by_ticket(ticket_id).user_feedback == AiFeedback.HELPFUL
    feedback, status_changed = uow.event_bus.published
    assert isinstance(feedback, AiFeedbackGiven) and feedback.is_helpful
    assert isinstance(status_changed, TicketStatusChanged)
    assert (status_changed.old_status, status_changed.new_status) == (S.AI_ANSWERED, S.CLOSED)


def test_unhelpful_answer_escalates_ticket(uow):
    ticket_id = add_answered_ticket(uow)

    evaluate(uow, ticket_id, is_helpful=False)

    assert uow.tickets.get(ticket_id).status == S.ESCALATED
    assert uow.ai_responses.get_by_ticket(ticket_id).user_feedback == AiFeedback.NOT_HELPFUL


@pytest.mark.parametrize("actor_id", [OTHER_USER, ADMIN])
def test_only_requester_can_evaluate(uow, actor_id):
    ticket_id = add_answered_ticket(uow)

    with pytest.raises(PermissionDeniedError):
        evaluate(uow, ticket_id, is_helpful=True, actor_id=actor_id)


def test_answer_cannot_be_evaluated_twice(uow):
    ticket_id = add_answered_ticket(uow)
    evaluate(uow, ticket_id, is_helpful=False)

    with pytest.raises(DomainError):
        evaluate(uow, ticket_id, is_helpful=True)
    assert uow.tickets.get(ticket_id).status == S.ESCALATED


def test_low_confidence_ticket_has_nothing_to_evaluate(uow):
    """İş kuralı 4 ile eskale edilen talepte yanıt kullanıcıya gösterilmedi; değerlendirme yok."""
    ticket_id = add_answered_ticket(uow, status=S.ESCALATED)

    with pytest.raises(DomainError, match="'Eskale edildi' durumundaki"):
        evaluate(uow, ticket_id, is_helpful=True)
    assert uow.ai_responses.get_by_ticket(ticket_id).user_feedback is None


def test_missing_ai_response_raises_not_found(uow):
    ticket_id = add_answered_ticket(uow, with_response=False)

    with pytest.raises(NotFoundError, match="AI yanıtı bulunamadı"):
        evaluate(uow, ticket_id, is_helpful=True)


def test_ai_feedback_endpoint(uow):
    app = create_app()
    app.dependency_overrides[get_unit_of_work] = lambda: uow
    ticket_id = add_answered_ticket(uow)

    response = TestClient(app).post(
        f"/tickets/{ticket_id}/ai-feedback", json={"is_helpful": False}, headers={"X-User-Id": "1"}
    )

    assert response.status_code == 204
    assert uow.tickets.get(ticket_id).status == S.ESCALATED


# --- Ana akış (CLAUDE.md), gerçek PostgreSQL ---


def test_main_flow_end_to_end_on_real_database(session_factory):
    """Talep → AI yanıtı → "çözülmedi" → atama → teknisyen çözer → kullanıcı kapatır."""
    bus = InMemoryEventBus()
    register_subscribers(
        bus,
        make_auto_answer_handler=lambda: AutoAnswerTicketHandler(
            SqlAlchemyUnitOfWork(bus, session_factory), FakeAiSupport(), 0.6
        ),
    )
    statuses: list[TicketStatus] = []
    bus.subscribe(TicketStatusChanged, lambda e: statuses.append(e.new_status))

    uow = SqlAlchemyUnitOfWork(bus, session_factory)
    with uow:
        user = uow.users.add(User(full_name="A", email="it.flow@test.edu"))
        admin = uow.users.add(User(full_name="Y", email="it.flowa@test.edu", role=UserRole.ADMIN))
        tech = uow.users.add(
            User(full_name="T", email="it.flowt@test.edu", role=UserRole.TECHNICIAN)
        )
        uow.commit()

    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicket(
            actor_id=user.id,
            title="Yazıcı çıktı vermiyor",
            description="Kuyrukta bekliyor",
            category=TicketCategory.HARDWARE,
        )
    )
    EvaluateAiAnswerHandler(uow).handle(
        EvaluateAiAnswer(actor_id=user.id, ticket_id=ticket_id, is_helpful=False)
    )
    AssignTicketHandler(uow).handle(
        AssignTicket(actor_id=admin.id, ticket_id=ticket_id, technician_id=tech.id)
    )
    StartWorkHandler(uow).handle(StartWork(actor_id=tech.id, ticket_id=ticket_id))
    ResolveTicketHandler(uow).handle(ResolveTicket(actor_id=tech.id, ticket_id=ticket_id))
    CloseTicketHandler(uow).handle(CloseTicket(actor_id=user.id, ticket_id=ticket_id))

    assert statuses == [
        S.AI_ANSWERED,  # AI asistan (Observer ile)
        S.ESCALATED,  # kullanıcı: çözülmedi
        S.ASSIGNED,
        S.IN_PROGRESS,
        S.RESOLVED,
        S.CLOSED,
    ]
    with uow:
        response = uow.ai_responses.get_by_ticket(ticket_id)
    assert response.user_feedback == AiFeedback.NOT_HELPFUL
