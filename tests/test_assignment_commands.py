"""Zimmet command handler testleri."""

import pytest

from app.application.commands.assignments import (
    AssignDevice,
    AssignDeviceHandler,
    ReturnDevice,
    ReturnDeviceHandler,
)
from app.application.errors import NotFoundError, PermissionDeniedError
from app.domain.enums import DeviceStatus, UserRole
from app.domain.errors import BusinessRuleViolation
from app.domain.events import DeviceAssigned, DeviceReturned
from app.domain.inventory import Assignment, Device
from app.domain.user import User
from tests.fakes import FakeUnitOfWork


def setup_data(uow) -> tuple[int, int, int]:
    """Yönetici, kullanıcı ve depoda bir cihaz ekler; id'lerini döndürür."""
    admin = uow.users.add(User(full_name="Yönetici", email="a@x.edu", role=UserRole.ADMIN))
    user = uow.users.add(User(full_name="Ayşe", email="u@x.edu", role=UserRole.USER))
    device = uow.devices.add(
        Device(asset_tag="PC-1", type="PC", brand="Dell", model="X", serial_number="S1")
    )
    return admin.id, user.id, device.id


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


def test_assign_creates_active_assignment_and_marks_device_assigned(uow):
    admin_id, user_id, device_id = setup_data(uow)

    assignment_id = AssignDeviceHandler(uow).handle(
        AssignDevice(actor_id=admin_id, device_id=device_id, user_id=user_id)
    )

    assignment = uow.assignments.get(assignment_id)
    assert assignment.is_active
    assert assignment.user_id == user_id
    assert assignment.assigned_by == admin_id
    assert uow.devices.get(device_id).status == DeviceStatus.ASSIGNED
    [event] = uow.event_bus.published
    assert isinstance(event, DeviceAssigned)
    assert (event.device_id, event.user_id, event.assignment_id) == (
        device_id,
        user_id,
        assignment_id,
    )


def test_assigned_device_cannot_be_assigned_again(uow):
    admin_id, user_id, device_id = setup_data(uow)
    handler = AssignDeviceHandler(uow)
    handler.handle(AssignDevice(actor_id=admin_id, device_id=device_id, user_id=user_id))

    with pytest.raises(BusinessRuleViolation, match="zaten zimmetli"):
        handler.handle(AssignDevice(actor_id=admin_id, device_id=device_id, user_id=user_id))

    assert len(uow.assignments.items) == 1


def test_active_assignment_record_blocks_assignment_even_if_status_is_inconsistent(uow):
    """İş kuralı 1'in ikinci güvencesi: durum IN_STOCK görünse bile aktif zimmet varsa reddet."""
    admin_id, user_id, device_id = setup_data(uow)
    uow.assignments.add(Assignment(device_id=device_id, user_id=user_id, assigned_by=admin_id))

    with pytest.raises(BusinessRuleViolation, match="aktif bir zimmeti var"):
        AssignDeviceHandler(uow).handle(
            AssignDevice(actor_id=admin_id, device_id=device_id, user_id=user_id)
        )


def test_assign_to_unknown_user_raises_not_found(uow):
    admin_id, _, device_id = setup_data(uow)

    with pytest.raises(NotFoundError, match="kullanıcı bulunamadı"):
        AssignDeviceHandler(uow).handle(
            AssignDevice(actor_id=admin_id, device_id=device_id, user_id=999)
        )
    assert uow.devices.get(device_id).status == DeviceStatus.IN_STOCK


def test_only_admin_can_assign(uow):
    _, user_id, device_id = setup_data(uow)

    with pytest.raises(PermissionDeniedError):
        AssignDeviceHandler(uow).handle(
            AssignDevice(actor_id=user_id, device_id=device_id, user_id=user_id)
        )


def test_return_closes_assignment_and_puts_device_back_in_stock(uow):
    admin_id, user_id, device_id = setup_data(uow)
    assignment_id = AssignDeviceHandler(uow).handle(
        AssignDevice(actor_id=admin_id, device_id=device_id, user_id=user_id)
    )

    ReturnDeviceHandler(uow).handle(ReturnDevice(actor_id=admin_id, device_id=device_id))

    assignment = uow.assignments.get(assignment_id)
    assert assignment.returned_at is not None
    assert uow.devices.get(device_id).status == DeviceStatus.IN_STOCK
    assert isinstance(uow.event_bus.published[-1], DeviceReturned)
    assert uow.event_bus.published[-1].user_id == user_id


def test_return_without_active_assignment_is_rejected(uow):
    admin_id, _, device_id = setup_data(uow)

    with pytest.raises(BusinessRuleViolation, match="aktif bir zimmeti yok"):
        ReturnDeviceHandler(uow).handle(ReturnDevice(actor_id=admin_id, device_id=device_id))


def test_device_in_repair_cannot_be_returned_and_assignment_stays_active(uow):
    admin_id, user_id, device_id = setup_data(uow)
    assignment_id = AssignDeviceHandler(uow).handle(
        AssignDevice(actor_id=admin_id, device_id=device_id, user_id=user_id)
    )
    device = uow.devices.get(device_id)
    device.status = DeviceStatus.IN_REPAIR  # bakım akışı 4c'de; burada durumu elle kuruyoruz
    uow.devices.update(device)

    with pytest.raises(BusinessRuleViolation, match="bakımda"):
        ReturnDeviceHandler(uow).handle(ReturnDevice(actor_id=admin_id, device_id=device_id))

    assert uow.assignments.get(assignment_id).is_active
