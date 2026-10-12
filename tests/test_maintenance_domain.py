"""İş kuralı 2'nin domain testleri: bakım açılınca IN_REPAIR, kapanınca önceki durum."""

import pytest

from app.domain.enums import DeviceStatus, MaintenanceType
from app.domain.errors import BusinessRuleViolation
from app.domain.inventory import Device, MaintenanceRecord


def make_device(status: DeviceStatus) -> Device:
    return Device(
        id=1, asset_tag="PC-1", type="PC", brand="Dell", model="X", serial_number="S1", status=status
    )


def open_record(device: Device) -> MaintenanceRecord:
    return MaintenanceRecord.open(
        device=device, technician_id=5, type=MaintenanceType.REPAIR, description="Fan arızası"
    )


@pytest.mark.parametrize("initial_status", [DeviceStatus.IN_STOCK, DeviceStatus.ASSIGNED])
def test_device_returns_to_its_previous_status_after_maintenance(initial_status):
    device = make_device(initial_status)

    record = open_record(device)
    assert device.status == DeviceStatus.IN_REPAIR
    assert record.previous_device_status == initial_status
    assert record.is_open

    record.complete(device)
    assert device.status == initial_status
    assert not record.is_open


@pytest.mark.parametrize(
    "status, message",
    [
        (DeviceStatus.RETIRED, "Hurdaya ayrılmış"),
        (DeviceStatus.IN_REPAIR, "zaten açık bir bakım"),
    ],
)
def test_maintenance_cannot_be_opened(status, message):
    device = make_device(status)
    with pytest.raises(BusinessRuleViolation, match=message):
        open_record(device)
    assert device.status == status


def test_maintenance_cannot_be_completed_twice():
    device = make_device(DeviceStatus.IN_STOCK)
    record = open_record(device)
    record.complete(device)

    with pytest.raises(BusinessRuleViolation, match="zaten tamamlanmış"):
        record.complete(device)
    assert device.status == DeviceStatus.IN_STOCK
