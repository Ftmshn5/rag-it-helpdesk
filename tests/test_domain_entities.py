from datetime import UTC, datetime

from app.domain.enums import TicketCategory, TicketStatus, UserRole
from app.domain.inventory import Assignment
from app.domain.ticket import Ticket
from app.domain.user import User


def test_assignment_is_active_until_returned():
    assignment = Assignment(device_id=1, user_id=2, assigned_by=3)
    assert assignment.is_active

    assignment.returned_at = datetime.now(UTC)
    assert not assignment.is_active


def test_new_ticket_starts_open_without_modifiers():
    ticket = Ticket(
        title="Yazıcı çalışmıyor",
        description="Kağıt sıkışması uyarısı veriyor",
        category=TicketCategory.HARDWARE,
        requester_id=1,
    )
    assert ticket.status == TicketStatus.OPEN
    assert ticket.modifiers == []


def test_tickets_do_not_share_modifier_list():
    first = Ticket(title="a", description="a", category=TicketCategory.NETWORK, requester_id=1)
    second = Ticket(title="b", description="b", category=TicketCategory.NETWORK, requester_id=1)

    first.modifiers.append("URGENT")

    assert second.modifiers == []


def test_user_is_technician_only_for_technician_role():
    assert User(full_name="T", email="t@x.edu", role=UserRole.TECHNICIAN).is_technician
    assert not User(full_name="A", email="a@x.edu", role=UserRole.ADMIN).is_technician
