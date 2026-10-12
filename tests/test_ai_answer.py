"""UC-14 (AI otomatik yanıt) ve iş kuralı 4 (düşük güvende eskalasyon) testleri."""

import pytest

from app.application.commands.ai_answers import AutoAnswerTicket, AutoAnswerTicketHandler
from app.application.commands.tickets import CreateTicket, CreateTicketHandler
from app.application.interfaces.ai_support import AiSupportFacade, AutoAnswer
from app.core.event_subscriptions import register_subscribers
from app.domain.enums import TicketCategory, TicketStatus
from app.domain.events import AiAnswerRecorded, TicketStatusChanged
from app.domain.ticket import Ticket
from app.domain.user import User
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from tests.fakes import FakeUnitOfWork

THRESHOLD = 0.6


class FixedAiSupport(AiSupportFacade):
    """Her talebe verilen güvenle aynı yanıtı döndüren test dublörü."""

    def __init__(self, confidence: float) -> None:
        self.confidence = confidence

    def try_auto_resolve(self, ticket: Ticket) -> AutoAnswer:
        return AutoAnswer(answer="Yeniden başlatın.", confidence=self.confidence, sources=["k.md"])


class BrokenAiSupport(AiSupportFacade):
    def try_auto_resolve(self, ticket: Ticket) -> AutoAnswer:
        raise ConnectionError("Ollama'ya bağlanılamadı")


# --- Domain: iş kuralı 4 ---


def make_ticket() -> Ticket:
    return Ticket(title="t", description="d", category=TicketCategory.SOFTWARE, requester_id=1)


@pytest.mark.parametrize(
    "confidence, shown, status",
    [
        (0.85, True, TicketStatus.AI_ANSWERED),
        (0.60, True, TicketStatus.AI_ANSWERED),  # eşiğin kendisi yeterli
        (0.59, False, TicketStatus.ESCALATED),
        (None, False, TicketStatus.ESCALATED),  # AI hiç yanıt üretemedi
    ],
)
def test_receive_ai_answer_applies_threshold(confidence, shown, status):
    ticket = make_ticket()
    assert ticket.receive_ai_answer(confidence, THRESHOLD) is shown
    assert ticket.status == status


# --- Handler ---


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.tickets.add(make_ticket())  # id=1
    return uow


def run(uow, ai_support) -> None:
    AutoAnswerTicketHandler(uow, ai_support, THRESHOLD).handle(AutoAnswerTicket(ticket_id=1))


def test_confident_answer_is_saved_and_ticket_becomes_ai_answered(uow):
    run(uow, FixedAiSupport(0.8))

    assert uow.tickets.get(1).status == TicketStatus.AI_ANSWERED
    response = uow.ai_responses.get_by_ticket(1)
    assert (response.answer, response.confidence, response.sources) == (
        "Yeniden başlatın.",
        0.8,
        ["k.md"],
    )
    recorded, status_changed = uow.event_bus.published
    assert isinstance(recorded, AiAnswerRecorded) and not recorded.escalated
    assert isinstance(status_changed, TicketStatusChanged)
    assert status_changed.actor_id is None  # geçişi AI yaptı
    assert status_changed.new_status == TicketStatus.AI_ANSWERED


def test_low_confidence_escalates_but_keeps_answer_for_statistics(uow):
    run(uow, FixedAiSupport(0.3))

    assert uow.tickets.get(1).status == TicketStatus.ESCALATED
    assert uow.ai_responses.get_by_ticket(1).confidence == 0.3
    assert uow.event_bus.published[0].escalated


def test_ai_failure_escalates_instead_of_leaving_ticket_open(uow, caplog):
    run(uow, BrokenAiSupport())

    assert uow.tickets.get(1).status == TicketStatus.ESCALATED
    assert uow.ai_responses.get_by_ticket(1) is None
    assert uow.event_bus.published[0].confidence is None
    assert "AI yanıtı üretilemedi" in caplog.text


def test_already_processed_ticket_is_skipped(uow):
    run(uow, FixedAiSupport(0.8))
    uow.event_bus.published.clear()

    run(uow, FixedAiSupport(0.8))  # aynı olay ikinci kez gelirse

    assert uow.event_bus.published == []
    assert len(uow.ai_responses.items) == 1


class TrackingAiSupport(AiSupportFacade):
    """AI çağrılırken transaction açık mı, kaydeder; isteğe bağlı olarak talebi değiştirir."""

    def __init__(self, uow: FakeUnitOfWork, change_ticket_to: TicketStatus | None = None) -> None:
        self.uow = uow
        self.change_ticket_to = change_ticket_to
        self.uow_was_open: bool | None = None

    def try_auto_resolve(self, ticket: Ticket) -> AutoAnswer:
        self.uow_was_open = self.uow.is_open
        if self.change_ticket_to:
            # AI düşünürken başka bir istek talebi değiştirdi
            changed = self.uow.tickets.get(ticket.id)
            changed.status = self.change_ticket_to
            self.uow.tickets.update(changed)
        return AutoAnswer(answer="Yeniden başlatın.", confidence=0.9, sources=[])


class TransactionTrackingUow(FakeUnitOfWork):
    is_open = False

    def __enter__(self):
        self.is_open = True
        return super().__enter__()

    def __exit__(self, *exc_info) -> None:
        super().__exit__(*exc_info)
        self.is_open = False


def test_ai_is_called_outside_of_any_transaction():
    uow = TransactionTrackingUow()
    uow.tickets.add(make_ticket())
    ai = TrackingAiSupport(uow)

    run(uow, ai)

    assert ai.uow_was_open is False
    assert uow.tickets.get(1).status == TicketStatus.AI_ANSWERED


def test_answer_is_discarded_if_ticket_changed_while_ai_was_thinking():
    uow = TransactionTrackingUow()
    uow.tickets.add(make_ticket())

    run(uow, TrackingAiSupport(uow, change_ticket_to=TicketStatus.ESCALATED))

    assert uow.tickets.get(1).status == TicketStatus.ESCALATED
    assert uow.ai_responses.get_by_ticket(1) is None
    assert uow.event_bus.published == []


# --- Observer bağlantısı: TicketCreated → AI ---


def wire(bus, uow, ai_support) -> None:
    register_subscribers(
        bus, make_auto_answer_handler=lambda: AutoAnswerTicketHandler(uow, ai_support, THRESHOLD)
    )


@pytest.mark.parametrize(
    "title, expected_status",
    [
        ("Şifremi unuttum", TicketStatus.AI_ANSWERED),
        ("Monitörden duman çıkıyor", TicketStatus.ESCALATED),
    ],
)
def test_creating_ticket_triggers_ai_through_event_bus(title, expected_status):
    bus = InMemoryEventBus()
    uow = FakeUnitOfWork(bus)
    wire(bus, uow, FakeAiSupport())
    requester = uow.users.add(User(full_name="Ayşe", email="a@x.edu"))

    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicket(
            actor_id=requester.id, title=title, description="", category=TicketCategory.SOFTWARE
        )
    )

    assert uow.tickets.get(ticket_id).status == expected_status


def test_create_ticket_handler_does_not_know_about_ai():
    """Observer'ın kanıtı: dinleyici yoksa talep yalnızca açılır, AI çalışmaz."""
    uow = FakeUnitOfWork(InMemoryEventBus())
    requester = uow.users.add(User(full_name="Ayşe", email="a@x.edu"))

    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicket(
            actor_id=requester.id, title="Şifremi unuttum", description="", category=TicketCategory.ACCOUNT
        )
    )

    assert uow.tickets.get(ticket_id).status == TicketStatus.OPEN


# --- Gerçek PostgreSQL ---


def test_ai_flow_on_real_database(session_factory):
    bus = InMemoryEventBus()
    register_subscribers(
        bus,
        make_auto_answer_handler=lambda: AutoAnswerTicketHandler(
            SqlAlchemyUnitOfWork(bus, session_factory), FakeAiSupport(), THRESHOLD
        ),
    )
    uow = SqlAlchemyUnitOfWork(bus, session_factory)
    with uow:
        requester = uow.users.add(User(full_name="A", email="it.ai@test.edu"))
        uow.commit()

    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicket(
            actor_id=requester.id,
            title="eduroam bağlanmıyor",
            description="Telefonumdan bağlanamıyorum",
            category=TicketCategory.NETWORK,
        )
    )

    with uow:
        ticket = uow.tickets.get(ticket_id)
        response = uow.ai_responses.get_by_ticket(ticket_id)
    assert ticket.status == TicketStatus.AI_ANSWERED
    assert response.confidence == 0.75
    assert response.sources == ["knowledge/kablosuz-ag-baglantisi.md"]
