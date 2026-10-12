from datetime import date

import pytest

from app.domain.enums import DeviceStatus
from app.domain.errors import BusinessRuleViolation
from app.domain.inventory import Device


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
