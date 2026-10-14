"""Chain of Responsibility testleri: destek seviyeleri ve eskalasyon zinciri.

AI (L0) → Teknisyen (L1) → Kıdemli teknisyen (L2). Zincir talebin hangi
seviyeye çıkacağına, State ise eskalasyonun hangi durumda yapılabileceğine
karar verir; iş kuralı 12: L2 talep yalnızca kıdemli teknisyene atanır.
"""

import pytest

from app.domain.enums import SupportLevel, TicketCategory, TicketStatus, UserRole
from app.domain.errors import (
    HighestSupportLevelError,
    InsufficientSupportLevelError,
    InvalidTicketTransitionError,
)
from app.domain.support_tier import SUPPORT_CHAIN, SupportChain
from app.domain.ticket import Ticket
from app.domain.user import User

S = TicketStatus
L = SupportLevel
TECHNICIAN = User(id=10, full_name="Ali", email="ali@x.edu", role=UserRole.TECHNICIAN)
SENIOR = User(id=11, full_name="Elif", email="elif@x.edu", role=UserRole.TECHNICIAN, support_level=L.TIER_2)


def make_ticket(status: TicketStatus = S.OPEN, level: SupportLevel = L.AI, assignee_id: int | None = None) -> Ticket:
    return Ticket(
        title="Yazıcı çalışmıyor",
        description="Kâğıt sıkışıyor",
        category=TicketCategory.HARDWARE,
        requester_id=1,
        status=status,
        support_level=level,
        assignee_id=assignee_id,
    )


# --- Zincirin kendisi ---


@pytest.mark.parametrize(("current", "expected"), [(L.AI, L.TIER_1), (L.TIER_1, L.TIER_2)])
def test_chain_passes_request_to_the_first_tier_that_accepts_it(current, expected):
    assert SupportChain().escalate_from(current) == expected


def test_end_of_chain_means_highest_level():
    with pytest.raises(HighestSupportLevelError):
        SupportChain().escalate_from(L.TIER_2)


@pytest.mark.parametrize(
    ("level", "technician", "allowed"),
    [
        (L.AI, TECHNICIAN, False),  # AI seviyesindeki talep önce eskale edilmeli
        (L.TIER_1, TECHNICIAN, True),
        (L.TIER_1, SENIOR, True),  # kıdemli teknisyen alt seviyeye de bakabilir
        (L.TIER_2, TECHNICIAN, False),
        (L.TIER_2, SENIOR, True),
    ],
)
def test_each_tier_knows_who_can_handle_it(level, technician, allowed):
    assert SUPPORT_CHAIN.tier(level).can_be_handled_by(technician) is allowed


# --- Kullanıcının destek seviyesi ---


def test_technician_defaults_to_tier_1_and_other_roles_have_no_level():
    assert TECHNICIAN.support_level == L.TIER_1
    assert User(full_name="A", email="a@x.edu", support_level=L.TIER_2).support_level is None


# --- Ticket: State + zincir birlikte ---


def test_new_ticket_starts_at_ai_level():
    assert make_ticket().support_level == L.AI


@pytest.mark.parametrize("status", [S.OPEN, S.AI_ANSWERED])
def test_ai_escalation_hands_ticket_to_technicians(status):
    """İş kuralı 4 ve UC-02: AI çözemedi → L1."""
    ticket = make_ticket(status)
    ticket.escalate()
    assert (ticket.status, ticket.support_level) == (S.ESCALATED, L.TIER_1)


@pytest.mark.parametrize("status", [S.ASSIGNED, S.IN_PROGRESS])
def test_technician_escalates_to_senior_level_and_releases_the_ticket(status):
    """UC-07: teknisyen → L2; talep yeniden atama kuyruğuna döner."""
    ticket = make_ticket(status, L.TIER_1, assignee_id=TECHNICIAN.id)

    ticket.escalate()

    assert (ticket.status, ticket.support_level, ticket.assignee_id) == (S.ESCALATED, L.TIER_2, None)


def test_senior_level_ticket_cannot_be_escalated_further():
    ticket = make_ticket(S.IN_PROGRESS, L.TIER_2, assignee_id=SENIOR.id)

    with pytest.raises(HighestSupportLevelError):
        ticket.escalate()

    # Hata hiçbir alanı değiştirmez
    assert (ticket.status, ticket.support_level, ticket.assignee_id) == (S.IN_PROGRESS, L.TIER_2, SENIOR.id)


def test_state_still_decides_when_escalation_is_possible():
    ticket = make_ticket(S.ESCALATED, L.TIER_1)
    with pytest.raises(InvalidTicketTransitionError):
        ticket.escalate()
    assert ticket.support_level == L.TIER_1


def test_senior_ticket_is_assigned_only_to_senior_technician():
    """İş kuralı 12."""
    ticket = make_ticket(S.ESCALATED, L.TIER_2)

    with pytest.raises(InsufficientSupportLevelError):
        ticket.assign_to(TECHNICIAN)
    assert (ticket.status, ticket.assignee_id) == (S.ESCALATED, None)

    ticket.assign_to(SENIOR)
    assert (ticket.status, ticket.assignee_id) == (S.ASSIGNED, SENIOR.id)


def test_full_chain_ai_to_technician_to_senior():
    ticket = make_ticket()

    ticket.escalate()  # AI: düşük güven
    ticket.assign_to(TECHNICIAN)
    ticket.start_work()
    ticket.escalate()  # UC-07
    ticket.assign_to(SENIOR)
    ticket.start_work()
    ticket.resolve()

    assert (ticket.status, ticket.support_level, ticket.assignee_id) == (S.RESOLVED, L.TIER_2, SENIOR.id)


def test_reopen_keeps_the_support_level():
    """Yeniden açılan talep aynı seviyede kalır; seviye yalnızca eskalasyonla artar."""
    ticket = make_ticket(S.RESOLVED, L.TIER_2, assignee_id=SENIOR.id)
    ticket.reopen()
    assert (ticket.status, ticket.support_level) == (S.ESCALATED, L.TIER_2)
