"""Envanter akışlarının gerçek PostgreSQL üzerinde uçtan uca testleri.

Test sonunda transaction geri alınır; geliştirme verisi değişmez.
"""

import pytest

from app.application.commands.assignments import (
    AssignDevice,
    AssignDeviceHandler,
    ReturnDevice,
    ReturnDeviceHandler,
)
from app.application.commands.maintenance import (
    CompleteMaintenance,
    CompleteMaintenanceHandler,
    StartMaintenance,
    StartMaintenanceHandler,
)
from app.domain.enums import DeviceStatus, MaintenanceType, UserRole
from app.domain.errors import DomainError
from app.domain.inventory import Device
from app.domain.user import User


def test_assign_return_and_reassign_cycle_on_real_database(sqlalchemy_uow):
    uow = sqlalchemy_uow
    with uow:
        admin = uow.users.add(User(full_name="Y", email="it.admin@test.edu", role=UserRole.ADMIN))
        first = uow.users.add(User(full_name="A", email="it.first@test.edu"))
        second = uow.users.add(User(full_name="B", email="it.second@test.edu"))
        device = uow.devices.add(
            Device(asset_tag="IT-0001", type="PC", brand="Dell", model="X", serial_number="IT-S1")
        )
        uow.commit()

    assign, give_back = AssignDeviceHandler(uow), ReturnDeviceHandler(uow)

    first_id = assign.handle(AssignDevice(actor_id=admin.id, device_id=device.id, user_id=first.id))
    give_back.handle(ReturnDevice(actor_id=admin.id, device_id=device.id))
    # Koşullu benzersiz indeks yalnızca AKTİF zimmeti sınırlar: iade sonrası yeni zimmet serbest
    second_id = assign.handle(
        AssignDevice(actor_id=admin.id, device_id=device.id, user_id=second.id)
    )

    with uow:
        assert uow.devices.get(device.id).status == DeviceStatus.ASSIGNED
        assert not uow.assignments.get(first_id).is_active
        active = uow.assignments.get_active_for_device(device.id)
        assert active.id == second_id
        assert active.user_id == second.id


def test_assigned_device_maintenance_cycle_on_real_database(sqlalchemy_uow):
    """Zimmetli cihaz bakıma girer, bakımdayken iade alınamaz, bakım bitince yine zimmetli."""
    uow = sqlalchemy_uow
    with uow:
        admin = uow.users.add(User(full_name="Y", email="it.admin@test.edu", role=UserRole.ADMIN))
        tech = uow.users.add(
            User(full_name="T", email="it.tech@test.edu", role=UserRole.TECHNICIAN)
        )
        owner = uow.users.add(User(full_name="A", email="it.owner@test.edu"))
        device = uow.devices.add(
            Device(asset_tag="IT-0002", type="PC", brand="Dell", model="X", serial_number="IT-S2")
        )
        uow.commit()

    AssignDeviceHandler(uow).handle(
        AssignDevice(actor_id=admin.id, device_id=device.id, user_id=owner.id)
    )
    record_id = StartMaintenanceHandler(uow).handle(
        StartMaintenance(
            actor_id=tech.id,
            device_id=device.id,
            type=MaintenanceType.PART_REPLACEMENT,
            description="SSD değişimi",
        )
    )

    with pytest.raises(DomainError, match="bakımda"):
        ReturnDeviceHandler(uow).handle(ReturnDevice(actor_id=admin.id, device_id=device.id))

    CompleteMaintenanceHandler(uow).handle(
        CompleteMaintenance(actor_id=tech.id, maintenance_record_id=record_id)
    )

    with uow:
        assert uow.devices.get(device.id).status == DeviceStatus.ASSIGNED
        assert uow.assignments.get_active_for_device(device.id).user_id == owner.id
        assert uow.maintenance_records.get_open_for_device(device.id) is None
        assert uow.maintenance_records.get(record_id).completed_at is not None
