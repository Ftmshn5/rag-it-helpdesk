"""Ticket command handler testleri."""

import pytest

from app.application.commands.tickets import (
    CreateTicket,
    CreateTicketHandler,
    SetTicketUrgency,
    SetTicketUrgencyHandler,
)
from app.application.errors import NotFoundError, PermissionDeniedError
from app.domain.enums import TicketCategory, TicketModifier, UserRole
from app.domain.events import TicketCreated, TicketUrgencyChanged
from app.domain.user import User
from tests.fakes import FakeUnitOfWork


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.users.add(User(full_name="Ayşe", email="ayse@x.edu"))  # 1
    uow.users.add(User(full_name="Dekan", email="dekan@x.edu", is_vip=True))  # 2
    uow.users.add(User(full_name="Yönetici", email="admin@x.edu", role=UserRole.ADMIN))  # 3
    return uow


USER_ID, VIP_ID, ADMIN_ID = 1, 2, 3


def create(uow, actor_id=USER_ID, **overrides) -> int:
    values = dict(
        actor_id=actor_id,
        title="Yazıcı çalışmıyor",
        description="Kağıt sıkışıyor",
        category=TicketCategory.HARDWARE,
    )
    return CreateTicketHandler(uow).handle(CreateTicket(**(values | overrides)))


def test_regular_user_ticket_has_basic_sla(uow):
    ticket_id = create(uow)

    assert uow.tickets.get(ticket_id).modifiers == []
    [event] = uow.event_bus.published
    assert isinstance(event, TicketCreated)
    assert (event.sla_hours, event.priority_score) == (72, 10)


def test_vip_requester_gets_vip_modifier_automatically(uow):
    ticket_id = create(uow, actor_id=VIP_ID)

    assert uow.tickets.get(ticket_id).modifiers == [TicketModifier.VIP]
    assert uow.event_bus.published[0].sla_hours == 24


def test_urgent_vip_ticket_uses_full_decorator_chain(uow):
    create(uow, actor_id=VIP_ID, is_urgent=True)

    event = uow.event_bus.published[0]
    assert (event.sla_hours, event.priority_score) == (4, 80)


def test_unknown_device_is_rejected(uow):
    with pytest.raises(NotFoundError, match="Cihaz bulunamadı"):
        create(uow, device_id=99)
    assert uow.tickets.items == {}


def test_admin_marks_ticket_urgent_and_sla_tightens(uow):
    ticket_id = create(uow)
    uow.event_bus.published.clear()

    SetTicketUrgencyHandler(uow).handle(
        SetTicketUrgency(actor_id=ADMIN_ID, ticket_id=ticket_id, is_urgent=True)
    )

    assert uow.tickets.get(ticket_id).is_urgent
    [event] = uow.event_bus.published
    assert isinstance(event, TicketUrgencyChanged)
    assert (event.is_urgent, event.sla_hours) == (True, 4)


def test_unchanged_urgency_produces_no_event(uow):
    ticket_id = create(uow, is_urgent=True)
    uow.event_bus.published.clear()

    SetTicketUrgencyHandler(uow).handle(
        SetTicketUrgency(actor_id=ADMIN_ID, ticket_id=ticket_id, is_urgent=True)
    )

    assert uow.event_bus.published == []


def test_only_admin_can_change_urgency(uow):
    ticket_id = create(uow)

    with pytest.raises(PermissionDeniedError):
        SetTicketUrgencyHandler(uow).handle(
            SetTicketUrgency(actor_id=USER_ID, ticket_id=ticket_id, is_urgent=True)
        )
