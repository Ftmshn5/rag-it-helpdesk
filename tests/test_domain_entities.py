from app.domain.enums import TicketCategory, TicketStatus, UserRole
from app.domain.inventory import Assignment
from app.domain.ticket import Ticket
from app.domain.user import User


def test_assignment_is_active_until_returned():
    assignment = Assignment(device_id=1, user_id=2, assigned_by=3)
    assert assignment.is_active

    assignment.close()
    assert not assignment.is_active
    assert assignment.returned_at is not None


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

    first.set_urgent(True)

    assert second.modifiers == []


def test_modifiers_cannot_be_changed_from_outside():
    """Kapsülleme: modifiers bir kopya döner; listeyi değiştirmek talebi etkilemez."""
    ticket = Ticket(title="a", description="a", category=TicketCategory.NETWORK, requester_id=1)
    ticket.modifiers.append("URGENT")
    assert ticket.modifiers == []


def test_entity_fields_are_read_only():
    """Kapsülleme: durum yalnızca iş metotlarıyla değişir (iş kuralı 6)."""
    import pytest

    from app.domain.enums import DeviceStatus
    from app.domain.inventory import Device

    device = Device(asset_tag="PC-1", type="PC", brand="B", model="M", serial_number="S")
    with pytest.raises(AttributeError):
        device.status = DeviceStatus.RETIRED
    ticket = Ticket(title="a", description="a", category=TicketCategory.NETWORK, requester_id=1)
    with pytest.raises(AttributeError):
        ticket.status = TicketStatus.CLOSED


def test_user_is_technician_only_for_technician_role():
    assert User(full_name="T", email="t@x.edu", role=UserRole.TECHNICIAN).is_technician
    assert not User(full_name="A", email="a@x.edu", role=UserRole.ADMIN).is_technician
