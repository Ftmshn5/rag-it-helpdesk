"""State deseni testleri: ticket yaşam döngüsü.

Geçiş matrisi testi, 7 durum × 8 işlemin tamamını dener. Diyagramdaki her ok
izin verilen tek hedefe gitmeli; diyagramda olmayan her geçiş hata verip
durumu değiştirmemeli.
"""

import pytest

from app.domain.enums import TicketCategory, TicketStatus, UserRole
from app.domain.errors import DomainError
from app.domain.ticket import Ticket
from app.domain.user import User

S = TicketStatus
TECHNICIAN = User(id=10, full_name="Ali", email="ali@x.edu", role=UserRole.TECHNICIAN)
OTHER_TECHNICIAN = User(id=11, full_name="Elif", email="elif@x.edu", role=UserRole.TECHNICIAN)

ACTIONS = {
    "record_ai_answer": lambda t: t.record_ai_answer(),
    "accept_ai_answer": lambda t: t.accept_ai_answer(),
    "escalate": lambda t: t.escalate(),
    "assign": lambda t: t.assign(TECHNICIAN),
    "start_work": lambda t: t.start_work(),
    "resolve": lambda t: t.resolve(),
    "close": lambda t: t.close(),
    "reopen": lambda t: t.reopen(),
}

# Diyagramın kendisi: (durum, işlem) → hedef durum. Burada olmayan her çift yasaktır.
ALLOWED_TRANSITIONS = {
    (S.OPEN, "record_ai_answer"): S.AI_ANSWERED,
    (S.OPEN, "escalate"): S.ESCALATED,
    (S.AI_ANSWERED, "accept_ai_answer"): S.RESOLVED,
    (S.AI_ANSWERED, "escalate"): S.ESCALATED,
    (S.ESCALATED, "assign"): S.ASSIGNED,
    (S.ASSIGNED, "assign"): S.ASSIGNED,
    (S.ASSIGNED, "start_work"): S.IN_PROGRESS,
    (S.IN_PROGRESS, "assign"): S.ASSIGNED,
    (S.IN_PROGRESS, "resolve"): S.RESOLVED,
    (S.RESOLVED, "close"): S.CLOSED,
    (S.RESOLVED, "reopen"): S.ESCALATED,
}


def make_ticket(status: TicketStatus = S.OPEN) -> Ticket:
    return Ticket(
        title="Wi-Fi yok",
        description="Bağlanmıyor",
        category=TicketCategory.NETWORK,
        requester_id=1,
        status=status,
    )


@pytest.mark.parametrize("status", list(TicketStatus))
@pytest.mark.parametrize("action", list(ACTIONS))
def test_transition_matrix(status, action):
    ticket = make_ticket(status)
    expected = ALLOWED_TRANSITIONS.get((status, action))

    if expected is None:
        with pytest.raises(DomainError, match="yapılamaz"):
            ACTIONS[action](ticket)
        assert ticket.status == status  # yasak geçiş durumu bozmaz
    else:
        ACTIONS[action](ticket)
        assert ticket.status == expected


# --- Uçtan uca yollar ---


def test_happy_path_ai_solves_the_problem():
    ticket = make_ticket()

    ticket.record_ai_answer()
    ticket.accept_ai_answer()
    ticket.close()

    assert ticket.status == S.CLOSED
    assert ticket.resolved_at is not None


def test_happy_path_technician_solves_the_problem():
    ticket = make_ticket()

    ticket.record_ai_answer()
    ticket.escalate()  # kullanıcı: çözülmedi
    ticket.assign(TECHNICIAN)
    ticket.start_work()
    ticket.resolve()
    ticket.close()

    assert ticket.status == S.CLOSED
    assert ticket.assignee_id == TECHNICIAN.id


def test_low_confidence_goes_straight_to_escalation():
    """İş kuralı 4: AI güveni düşükse AI_ANSWERED'a hiç uğramadan eskale edilir."""
    ticket = make_ticket()
    ticket.escalate()
    assert ticket.status == S.ESCALATED


def test_reopen_clears_resolution_time_and_keeps_previous_technician():
    ticket = make_ticket(S.ESCALATED)
    ticket.assign(TECHNICIAN)
    ticket.start_work()
    ticket.resolve()

    ticket.reopen()

    assert ticket.status == S.ESCALATED
    assert ticket.resolved_at is None
    assert ticket.assignee_id == TECHNICIAN.id  # bilgi korunur, yeniden atanabilir


def test_reassigning_in_progress_ticket_returns_it_to_assigned():
    ticket = make_ticket(S.ESCALATED)
    ticket.assign(TECHNICIAN)
    ticket.start_work()

    ticket.assign(OTHER_TECHNICIAN)

    assert ticket.status == S.ASSIGNED
    assert ticket.assignee_id == OTHER_TECHNICIAN.id


# --- İş kuralı 3 ---


@pytest.mark.parametrize("role", [UserRole.USER, UserRole.ADMIN])
def test_ticket_can_only_be_assigned_to_technician(role):
    ticket = make_ticket(S.ESCALATED)
    not_technician = User(id=20, full_name="X", email="x@x.edu", role=role)

    with pytest.raises(DomainError, match="yalnızca teknisyen"):
        ticket.assign(not_technician)

    assert ticket.status == S.ESCALATED
    assert ticket.assignee_id is None


# --- Hata mesajı ---


def test_error_message_names_the_current_status_in_turkish():
    ticket = make_ticket(S.CLOSED)
    with pytest.raises(DomainError) as error:
        ticket.reopen()
    assert str(error.value) == "'Kapandı' durumundaki talep için yeniden açma yapılamaz."


# --- Durumun diğer kurallara etkisi ---


@pytest.mark.parametrize(
    "status, accepts_contributions, allows_urgency_change",
    [
        (S.OPEN, True, True),
        (S.IN_PROGRESS, True, True),
        (S.RESOLVED, True, False),
        (S.CLOSED, False, False),
    ],
)
def test_state_flags(status, accepts_contributions, allows_urgency_change):
    state = make_ticket(status).state
    assert state.accepts_contributions is accepts_contributions
    assert state.allows_urgency_change is allows_urgency_change
