"""Kanban panosu (E2) testleri: sürükle-bırak ile durum değişikliği.

Panodaki taşıma yeni bir kural getirmez: hedef sütun bir geçişe çevrilir,
geçerliliğine State karar verir. Geçersiz taşımada State'in Türkçe mesajı
409 ile döner; arayüz onu toast olarak gösterir.
"""

import pytest
from fastapi.testclient import TestClient

from app.application.commands.ticket_workflow import MoveTicketCommand, MoveTicketHandler
from app.application.errors import PermissionDeniedError
from app.core.dependencies import get_unit_of_work
from app.domain.enums import SupportLevel, TicketCategory, TicketStatus, UserRole
from app.domain.errors import InvalidTicketTransitionError
from app.domain.events import TicketStatusChanged
from app.domain.ticket import Ticket
from app.domain.user import User
from app.main import create_app
from tests.fakes import FakeUnitOfWork

S = TicketStatus
REQUESTER, TECH, OTHER_TECH = 1, 2, 3


def make_ticket(status: TicketStatus) -> Ticket:
    return Ticket(
        title="Projeksiyon",
        description="-",
        category=TicketCategory.HARDWARE,
        requester_id=REQUESTER,
        status=status,
        assignee_id=TECH,
        support_level=SupportLevel.TIER_1,
    )


# --- Domain: hedef sütun → geçiş; geçerliliğine State karar verir ---


@pytest.mark.parametrize(
    ("start", "target"),
    [(S.ASSIGNED, S.IN_PROGRESS), (S.IN_PROGRESS, S.RESOLVED)],
)
def test_allowed_moves_apply_the_matching_transition(start, target):
    ticket = make_ticket(start)
    ticket.move_to(target)
    assert ticket.status == target


def test_state_rejects_skipping_a_step_with_its_own_message():
    """Atandı → Çözüldü: geçiş tanımlı (resolve) ama State 'Atandı' durumunda izin vermez."""
    ticket = make_ticket(S.ASSIGNED)

    with pytest.raises(InvalidTicketTransitionError, match="'Atandı' durumundaki talep için çözüldü"):
        ticket.move_to(S.RESOLVED)

    assert ticket.status == S.ASSIGNED


@pytest.mark.parametrize("target", [S.ASSIGNED, S.CLOSED, S.ESCALATED, S.OPEN])
def test_columns_without_a_board_transition_are_rejected(target):
    ticket = make_ticket(S.IN_PROGRESS)

    with pytest.raises(InvalidTicketTransitionError, match="sürükleyerek taşınamaz"):
        ticket.move_to(target)

    assert ticket.status == S.IN_PROGRESS


# --- Handler: yetki ve olay ---


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.users.add(User(full_name="Ayşe", email="ayse@x.edu"))
    uow.users.add(User(full_name="Ali", email="ali@x.edu", role=UserRole.TECHNICIAN))
    uow.users.add(User(full_name="Elif", email="elif@x.edu", role=UserRole.TECHNICIAN))
    return uow


def test_assigned_technician_moves_ticket_and_status_change_is_published(uow):
    ticket_id = uow.tickets.add(make_ticket(S.ASSIGNED)).id

    MoveTicketHandler(uow).handle(MoveTicketCommand(actor_id=TECH, ticket_id=ticket_id, target_status=S.IN_PROGRESS))

    assert uow.tickets.get(ticket_id).status == S.IN_PROGRESS
    [event] = uow.event_bus.published
    assert isinstance(event, TicketStatusChanged)
    assert (event.old_status, event.new_status, event.actor_id) == (S.ASSIGNED, S.IN_PROGRESS, TECH)


@pytest.mark.parametrize("actor_id", [OTHER_TECH, REQUESTER])
def test_only_assigned_technician_can_move(uow, actor_id):
    ticket_id = uow.tickets.add(make_ticket(S.ASSIGNED)).id
    with pytest.raises(PermissionDeniedError):
        MoveTicketHandler(uow).handle(
            MoveTicketCommand(actor_id=actor_id, ticket_id=ticket_id, target_status=S.IN_PROGRESS)
        )
    assert uow.tickets.get(ticket_id).status == S.ASSIGNED


# --- API: geçersiz taşımada 409 + State'in mesajı (arayüzde toast) ---


def test_move_endpoint(uow):
    ticket_id = uow.tickets.add(make_ticket(S.ASSIGNED)).id
    app = create_app()
    app.dependency_overrides[get_unit_of_work] = lambda: uow
    client = TestClient(app)
    headers = {"X-User-Id": str(TECH)}

    rejected = client.post(f"/tickets/{ticket_id}/move", json={"status": "RESOLVED"}, headers=headers)
    assert rejected.status_code == 409
    assert "'Atandı' durumundaki talep" in rejected.json()["detail"]

    assert client.post(f"/tickets/{ticket_id}/move", json={"status": "IN_PROGRESS"}, headers=headers).status_code == 204
    assert uow.tickets.get(ticket_id).status == S.IN_PROGRESS
    assert client.post(f"/tickets/{ticket_id}/move", json={"status": "YOK"}, headers=headers).status_code == 422
