from datetime import date

import pytest

from app.domain.enums import DeviceStatus
from app.domain.errors import BusinessRuleViolation
from app.domain.inventory import Assignment, Device


def make_device(status: DeviceStatus = DeviceStatus.IN_STOCK) -> Device:
    return Device(
        asset_tag="PC-1", type="Masaüstü", brand="Dell", model="X", serial_number="S1", status=status
    )


def test_update_details_changes_only_given_fields():
    device = make_device()
    device.update_details(location="B Blok 101", purchase_date=date(2024, 1, 1))

    assert device.location == "B Blok 101"
    assert device.purchase_date == date(2024, 1, 1)
    assert device.brand == "Dell"  # verilmedi → değişmedi


def test_in_stock_device_can_be_retired():
    device = make_device()
    device.retire()
    assert device.status == DeviceStatus.RETIRED


@pytest.mark.parametrize("status", [DeviceStatus.ASSIGNED, DeviceStatus.IN_REPAIR])
def test_device_in_use_cannot_be_retired(status):
    device = make_device(status)
    with pytest.raises(BusinessRuleViolation, match="Yalnızca depodaki"):
        device.retire()
    assert device.status == status


def test_retired_device_cannot_be_retired_again():
    with pytest.raises(BusinessRuleViolation, match="zaten hurdaya"):
        make_device(DeviceStatus.RETIRED).retire()


# --- Zimmet ---


def test_in_stock_device_can_be_assigned():
    device = make_device()
    device.assign()
    assert device.status == DeviceStatus.ASSIGNED


@pytest.mark.parametrize(
    "status, message",
    [
        (DeviceStatus.ASSIGNED, "zaten zimmetli"),
        (DeviceStatus.IN_REPAIR, "bakımda"),
        (DeviceStatus.RETIRED, "Hurdaya ayrılmış"),
    ],
)
def test_only_in_stock_device_can_be_assigned(status, message):
    device = make_device(status)
    with pytest.raises(BusinessRuleViolation, match=message):
        device.assign()
    assert device.status == status


def test_assigned_device_returns_to_stock():
    device = make_device(DeviceStatus.ASSIGNED)
    device.mark_returned()
    assert device.status == DeviceStatus.IN_STOCK


def test_device_in_repair_cannot_be_returned():
    device = make_device(DeviceStatus.IN_REPAIR)
    with pytest.raises(BusinessRuleViolation, match="Önce bakımı tamamlayın"):
        device.mark_returned()


def test_assignment_cannot_be_closed_twice():
    assignment = Assignment(device_id=1, user_id=2, assigned_by=3)
    assignment.close()
    assert not assignment.is_active
    with pytest.raises(BusinessRuleViolation, match="zaten iade"):
        assignment.close()
