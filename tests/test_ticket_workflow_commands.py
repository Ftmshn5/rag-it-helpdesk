"""Ticket iş akışı command handler testleri: kim, hangi durumda, ne yapabilir."""

import pytest

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
from app.application.errors import NotFoundError, PermissionDeniedError
from app.domain.enums import SupportLevel, TicketCategory, TicketStatus, UserRole
from app.domain.errors import DomainError
from app.domain.events import TicketCommentAdded, TicketStatusChanged
from app.domain.ticket import Ticket
from app.domain.user import User
from tests.fakes import FakeUnitOfWork

S = TicketStatus
REQUESTER, TECH, OTHER_TECH, ADMIN, STRANGER = 1, 2, 3, 4, 5


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.users.add(User(full_name="Ayşe", email="ayse@x.edu"))
    uow.users.add(User(full_name="Ali", email="ali@x.edu", role=UserRole.TECHNICIAN))
    uow.users.add(User(full_name="Elif", email="elif@x.edu", role=UserRole.TECHNICIAN))
    uow.users.add(User(full_name="Can", email="can@x.edu", role=UserRole.ADMIN))
    uow.users.add(User(full_name="Mehmet", email="mehmet@x.edu"))
    return uow


def add_ticket(uow, status=S.ESCALATED, assignee_id=None) -> int:
    ticket = uow.tickets.add(
        Ticket(
            title="Wi-Fi yok",
            description="Bağlanmıyor",
            category=TicketCategory.NETWORK,
            requester_id=REQUESTER,
            assignee_id=assignee_id,
            status=status,
            support_level=SupportLevel.TIER_1,  # AI'dan eskale edilmiş talepler L1'dedir
        )
    )
    return ticket.id


def status_of(uow, ticket_id) -> TicketStatus:
    return uow.tickets.get(ticket_id).status


# --- UC-10: atama ---


def test_admin_assigns_escalated_ticket_to_technician(uow):
    ticket_id = add_ticket(uow)

    AssignTicketHandler(uow).handle(
        AssignTicketCommand(actor_id=ADMIN, ticket_id=ticket_id, technician_id=TECH)
    )

    ticket = uow.tickets.get(ticket_id)
    assert (ticket.status, ticket.assignee_id) == (S.ASSIGNED, TECH)
    [event] = uow.event_bus.published
    assert isinstance(event, TicketStatusChanged)
    assert (event.old_status, event.new_status, event.actor_id, event.assignee_id) == (
        S.ESCALATED,
        S.ASSIGNED,
        ADMIN,
        TECH,
    )


def test_assigning_to_non_technician_violates_rule_3(uow):
    ticket_id = add_ticket(uow)

    with pytest.raises(DomainError, match="yalnızca teknisyen"):
        AssignTicketHandler(uow).handle(
            AssignTicketCommand(actor_id=ADMIN, ticket_id=ticket_id, technician_id=STRANGER)
        )
    assert status_of(uow, ticket_id) == S.ESCALATED
    assert uow.event_bus.published == []


def test_assigning_to_unknown_user_raises_not_found(uow):
    ticket_id = add_ticket(uow)
    with pytest.raises(NotFoundError, match="Atanacak kullanıcı"):
        AssignTicketHandler(uow).handle(
            AssignTicketCommand(actor_id=ADMIN, ticket_id=ticket_id, technician_id=99)
        )


def test_only_admin_can_assign(uow):
    ticket_id = add_ticket(uow)
    with pytest.raises(PermissionDeniedError):
        AssignTicketHandler(uow).handle(
            AssignTicketCommand(actor_id=TECH, ticket_id=ticket_id, technician_id=TECH)
        )


def test_open_ticket_cannot_be_assigned_before_ai(uow):
    """State kuralı handler üzerinden de geçerli: önce AI, sonra teknisyen."""
    ticket_id = add_ticket(uow, status=S.OPEN)
    with pytest.raises(DomainError, match="'Açık' durumundaki"):
        AssignTicketHandler(uow).handle(
            AssignTicketCommand(actor_id=ADMIN, ticket_id=ticket_id, technician_id=TECH)
        )


# --- UC-06: teknisyen ---


def test_assigned_technician_starts_and_resolves(uow):
    ticket_id = add_ticket(uow, status=S.ASSIGNED, assignee_id=TECH)

    StartWorkHandler(uow).handle(StartWorkCommand(actor_id=TECH, ticket_id=ticket_id))
    assert status_of(uow, ticket_id) == S.IN_PROGRESS

    ResolveTicketHandler(uow).handle(ResolveTicketCommand(actor_id=TECH, ticket_id=ticket_id))
    ticket = uow.tickets.get(ticket_id)
    assert ticket.status == S.RESOLVED
    assert ticket.resolved_at is not None
    assert [e.new_status for e in uow.event_bus.published] == [S.IN_PROGRESS, S.RESOLVED]


@pytest.mark.parametrize("actor_id", [OTHER_TECH, ADMIN, REQUESTER])
def test_only_assigned_technician_can_work_on_ticket(uow, actor_id):
    ticket_id = add_ticket(uow, status=S.ASSIGNED, assignee_id=TECH)

    with pytest.raises(PermissionDeniedError, match="size atanmamış"):
        StartWorkHandler(uow).handle(StartWorkCommand(actor_id=actor_id, ticket_id=ticket_id))


# --- Kapatma ve yeniden açma ---


@pytest.mark.parametrize("actor_id", [REQUESTER, ADMIN])
def test_requester_or_admin_closes_resolved_ticket(uow, actor_id):
    ticket_id = add_ticket(uow, status=S.RESOLVED, assignee_id=TECH)

    CloseTicketHandler(uow).handle(CloseTicketCommand(actor_id=actor_id, ticket_id=ticket_id))

    assert status_of(uow, ticket_id) == S.CLOSED


def test_technician_cannot_close_ticket(uow):
    ticket_id = add_ticket(uow, status=S.RESOLVED, assignee_id=TECH)
    with pytest.raises(PermissionDeniedError):
        CloseTicketHandler(uow).handle(CloseTicketCommand(actor_id=TECH, ticket_id=ticket_id))


def test_requester_reopens_resolved_ticket(uow):
    ticket_id = add_ticket(uow, status=S.RESOLVED, assignee_id=TECH)

    ReopenTicketHandler(uow).handle(ReopenTicketCommand(actor_id=REQUESTER, ticket_id=ticket_id))

    assert status_of(uow, ticket_id) == S.ESCALATED


@pytest.mark.parametrize("actor_id", [ADMIN, TECH])
def test_only_requester_can_reopen(uow, actor_id):
    ticket_id = add_ticket(uow, status=S.RESOLVED, assignee_id=TECH)
    with pytest.raises(PermissionDeniedError, match="yalnızca talep sahibi"):
        ReopenTicketHandler(uow).handle(ReopenTicketCommand(actor_id=actor_id, ticket_id=ticket_id))


def test_closed_ticket_cannot_be_reopened(uow):
    ticket_id = add_ticket(uow, status=S.CLOSED)
    with pytest.raises(DomainError, match="'Kapandı' durumundaki"):
        ReopenTicketHandler(uow).handle(ReopenTicketCommand(actor_id=REQUESTER, ticket_id=ticket_id))


# --- Not ---


@pytest.mark.parametrize("actor_id", [REQUESTER, TECH, ADMIN])
def test_participants_can_add_comment(uow, actor_id):
    ticket_id = add_ticket(uow, status=S.IN_PROGRESS, assignee_id=TECH)

    comment_id = AddCommentHandler(uow).handle(
        AddCommentCommand(actor_id=actor_id, ticket_id=ticket_id, content="Kablo değiştirildi.")
    )

    comment = uow.ticket_comments.get(comment_id)
    assert (comment.author_id, comment.content) == (actor_id, "Kablo değiştirildi.")
    assert status_of(uow, ticket_id) == S.IN_PROGRESS  # not durum değiştirmez
    assert isinstance(uow.event_bus.published[0], TicketCommentAdded)


def test_non_participant_cannot_comment(uow):
    ticket_id = add_ticket(uow, status=S.IN_PROGRESS, assignee_id=TECH)
    with pytest.raises(PermissionDeniedError, match="not ekleme yetkiniz yok"):
        AddCommentHandler(uow).handle(
            AddCommentCommand(actor_id=OTHER_TECH, ticket_id=ticket_id, content="x")
        )


def test_closed_ticket_rejects_comment(uow):
    ticket_id = add_ticket(uow, status=S.CLOSED, assignee_id=TECH)
    with pytest.raises(DomainError, match="Kapanmış talebe"):
        AddCommentHandler(uow).handle(
            AddCommentCommand(actor_id=REQUESTER, ticket_id=ticket_id, content="x")
        )
