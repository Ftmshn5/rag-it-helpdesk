import pytest

from app.domain.enums import TicketCategory, TicketModifier, TicketStatus
from app.domain.errors import DomainError
from app.domain.ticket import Ticket
from app.domain.user import User

VIP, URGENT = TicketModifier.VIP, TicketModifier.URGENT


def open_ticket(is_vip=False, is_urgent=False) -> Ticket:
    requester = User(id=7, full_name="A", email="a@x.edu", is_vip=is_vip)
    return Ticket.open(
        requester=requester,
        title="İnternet yok",
        description="Wi-Fi bağlanmıyor",
        category=TicketCategory.NETWORK,
        is_urgent=is_urgent,
    )


@pytest.mark.parametrize(
    "is_vip, is_urgent, expected",
    [
        (False, False, []),
        (True, False, [VIP]),
        (False, True, [URGENT]),
        (True, True, [VIP, URGENT]),
    ],
)
def test_open_derives_modifiers_from_requester_and_urgency(is_vip, is_urgent, expected):
    ticket = open_ticket(is_vip=is_vip, is_urgent=is_urgent)

    assert ticket.modifiers == expected
    assert ticket.status == TicketStatus.OPEN
    assert ticket.requester_id == 7


def test_set_urgent_adds_and_removes_only_urgent():
    ticket = open_ticket(is_vip=True)

    ticket.set_urgent(True)
    assert ticket.modifiers == [VIP, URGENT]

    ticket.set_urgent(False)
    assert ticket.modifiers == [VIP]  # VIP kullanıcıdan gelir, aciliyetle değişmez


def test_set_urgent_is_idempotent():
    ticket = open_ticket(is_urgent=True)
    ticket.set_urgent(True)
    assert ticket.modifiers == [URGENT]


@pytest.mark.parametrize("status", [TicketStatus.RESOLVED, TicketStatus.CLOSED])
def test_finished_ticket_urgency_cannot_change(status):
    ticket = Ticket(title="t", description="d", category=TicketCategory.NETWORK, requester_id=7, status=status)

    with pytest.raises(DomainError, match="aciliyeti değiştirilemez"):
        ticket.set_urgent(True)
