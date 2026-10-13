"""Cihaz command handler testleri (FakeUnitOfWork ile, veritabanı olmadan)."""

import pytest

from app.application.commands.devices import (
    RegisterDeviceCommand,
    RegisterDeviceHandler,
    RetireDeviceCommand,
    RetireDeviceHandler,
    UpdateDeviceDetailsCommand,
    UpdateDeviceDetailsHandler,
)
from app.application.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from app.domain.enums import DeviceStatus, UserRole
from app.domain.errors import DomainError
from app.domain.events import DeviceDetailsUpdated, DeviceRegistered, DeviceRetired
from app.domain.inventory import Device
from app.domain.user import User
from tests.fakes import FakeUnitOfWork


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.users.add(User(full_name="Yönetici", email="admin@x.edu", role=UserRole.ADMIN))  # id=1
    uow.users.add(User(full_name="Kullanıcı", email="user@x.edu", role=UserRole.USER))  # id=2
    return uow


ADMIN_ID, USER_ID = 1, 2


def register_command(**overrides) -> RegisterDeviceCommand:
    values = dict(
        actor_id=ADMIN_ID,
        asset_tag="PC-0100",
        type="Masaüstü",
        brand="Dell",
        model="OptiPlex",
        serial_number="SN-100",
    )
    return RegisterDeviceCommand(**(values | overrides))


def add_device(uow, status=DeviceStatus.IN_STOCK, asset_tag="PC-0001") -> Device:
    return uow.devices.add(
        Device(
            asset_tag=asset_tag,
            type="Masaüstü",
            brand="HP",
            model="ProDesk",
            serial_number=f"SN-{asset_tag}",
            status=status,
        )
    )


# --- Cihaz ekleme ---


def test_admin_registers_device_in_stock(uow):
    device_id = RegisterDeviceHandler(uow).handle(register_command())

    device = uow.devices.get(device_id)
    assert device.asset_tag == "PC-0100"
    assert device.status == DeviceStatus.IN_STOCK
    assert uow.committed
    assert uow.event_bus.published == [
        DeviceRegistered(
            device_id=device_id,
            asset_tag="PC-0100",
            occurred_at=uow.event_bus.published[0].occurred_at,
        )
    ]


def test_non_admin_cannot_register_device(uow):
    with pytest.raises(PermissionDeniedError):
        RegisterDeviceHandler(uow).handle(register_command(actor_id=USER_ID))

    assert uow.devices.items == {}
    assert not uow.committed


def test_unknown_actor_cannot_register_device(uow):
    with pytest.raises(AuthenticationError):
        RegisterDeviceHandler(uow).handle(register_command(actor_id=999))


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"serial_number": "SN-YENI"}, "demirbaş numarası zaten kayıtlı"),
        ({"asset_tag": "PC-YENI"}, "seri numaralı cihaz zaten kayıtlı"),
    ],
)
def test_duplicate_asset_tag_or_serial_is_rejected(uow, overrides, message):
    RegisterDeviceHandler(uow).handle(register_command())
    uow.event_bus.published.clear()

    with pytest.raises(DomainError, match=message):
        RegisterDeviceHandler(uow).handle(register_command(**overrides))

    assert len(uow.devices.items) == 1
    assert uow.event_bus.published == []


# --- Güncelleme ---


def test_update_changes_details_but_never_status(uow):
    device = add_device(uow, status=DeviceStatus.ASSIGNED)

    UpdateDeviceDetailsHandler(uow).handle(
        UpdateDeviceDetailsCommand(actor_id=ADMIN_ID, device_id=device.id, location="Kütüphane")
    )

    updated = uow.devices.get(device.id)
    assert updated.location == "Kütüphane"
    assert updated.status == DeviceStatus.ASSIGNED
    assert isinstance(uow.event_bus.published[0], DeviceDetailsUpdated)


def test_update_unknown_device_raises_not_found(uow):
    with pytest.raises(NotFoundError):
        UpdateDeviceDetailsHandler(uow).handle(
            UpdateDeviceDetailsCommand(actor_id=ADMIN_ID, device_id=42, location="X")
        )


# --- Hurdaya ayırma ---


def test_admin_retires_device_in_stock(uow):
    device = add_device(uow)

    RetireDeviceHandler(uow).handle(RetireDeviceCommand(actor_id=ADMIN_ID, device_id=device.id))

    assert uow.devices.get(device.id).status == DeviceStatus.RETIRED
    assert isinstance(uow.event_bus.published[0], DeviceRetired)


def test_assigned_device_cannot_be_retired_and_nothing_is_saved(uow):
    device = add_device(uow, status=DeviceStatus.ASSIGNED)

    with pytest.raises(DomainError):
        RetireDeviceHandler(uow).handle(RetireDeviceCommand(actor_id=ADMIN_ID, device_id=device.id))

    assert uow.devices.get(device.id).status == DeviceStatus.ASSIGNED
    assert not uow.committed
    assert uow.event_bus.published == []
