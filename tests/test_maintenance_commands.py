"""Bakım command handler testleri."""

import pytest

from app.application.commands.maintenance import (
    CompleteMaintenance,
    CompleteMaintenanceHandler,
    StartMaintenance,
    StartMaintenanceHandler,
)
from app.application.errors import NotFoundError, PermissionDeniedError
from app.domain.enums import DeviceStatus, MaintenanceType, UserRole
from app.domain.errors import BusinessRuleViolation
from app.domain.events import MaintenanceCompleted, MaintenanceStarted
from app.domain.inventory import Device
from app.domain.user import User
from tests.fakes import FakeUnitOfWork


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.users.add(User(full_name="Teknisyen", email="t@x.edu", role=UserRole.TECHNICIAN))  # 1
    uow.users.add(User(full_name="Yönetici", email="a@x.edu", role=UserRole.ADMIN))  # 2
    return uow


TECHNICIAN_ID, ADMIN_ID = 1, 2


def add_device(uow, status=DeviceStatus.ASSIGNED) -> Device:
    return uow.devices.add(
        Device(asset_tag="PC-1", type="PC", brand="Dell", model="X", serial_number="S1", status=status)
    )


def start(uow, device_id, actor_id=TECHNICIAN_ID, **overrides) -> int:
    values = dict(
        actor_id=actor_id,
        device_id=device_id,
        type=MaintenanceType.REPAIR,
        description="Ekran kartı değişimi",
    )
    return StartMaintenanceHandler(uow).handle(StartMaintenance(**(values | overrides)))


def test_start_maintenance_puts_device_in_repair_and_remembers_previous_status(uow):
    device = add_device(uow, DeviceStatus.ASSIGNED)

    record_id = start(uow, device.id)

    record = uow.maintenance_records.get(record_id)
    assert record.technician_id == TECHNICIAN_ID
    assert record.previous_device_status == DeviceStatus.ASSIGNED
    assert uow.devices.get(device.id).status == DeviceStatus.IN_REPAIR
    assert isinstance(uow.event_bus.published[0], MaintenanceStarted)


def test_complete_maintenance_restores_previous_status(uow):
    device = add_device(uow, DeviceStatus.ASSIGNED)
    record_id = start(uow, device.id)

    CompleteMaintenanceHandler(uow).handle(
        CompleteMaintenance(actor_id=TECHNICIAN_ID, maintenance_record_id=record_id)
    )

    assert uow.devices.get(device.id).status == DeviceStatus.ASSIGNED
    assert not uow.maintenance_records.get(record_id).is_open
    assert isinstance(uow.event_bus.published[-1], MaintenanceCompleted)


def test_second_open_maintenance_is_rejected(uow):
    device = add_device(uow)
    start(uow, device.id)

    with pytest.raises(BusinessRuleViolation, match="zaten açık bir bakım"):
        start(uow, device.id)
    assert len(uow.maintenance_records.items) == 1


def test_only_technician_can_start_maintenance(uow):
    device = add_device(uow)

    with pytest.raises(PermissionDeniedError):
        start(uow, device.id, actor_id=ADMIN_ID)
    assert uow.devices.get(device.id).status == DeviceStatus.ASSIGNED


def test_unknown_ticket_is_rejected_and_nothing_changes(uow):
    device = add_device(uow)

    with pytest.raises(NotFoundError, match="talep bulunamadı"):
        start(uow, device.id, ticket_id=99)
    assert uow.devices.get(device.id).status == DeviceStatus.ASSIGNED
    assert uow.maintenance_records.items == {}


def test_complete_unknown_record_raises_not_found(uow):
    with pytest.raises(NotFoundError, match="Bakım kaydı bulunamadı"):
        CompleteMaintenanceHandler(uow).handle(
            CompleteMaintenance(actor_id=TECHNICIAN_ID, maintenance_record_id=42)
        )
