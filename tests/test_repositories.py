"""Repository sözleşme testleri.

`uow` fixture'ı parametreli olduğu için her test iki kez çalışır: in-memory sahte
ve gerçek PostgreSQL ile. İkisi de geçiyorsa, handler testlerinde sahteyi
kullanmak güvenlidir.
"""

from datetime import UTC, datetime

import pytest

from app.domain.enums import DeviceStatus, TicketCategory, TicketModifier, UserRole
from app.domain.inventory import Assignment, Device
from app.domain.ticket import Ticket
from app.domain.user import User


def make_device(asset_tag: str = "TEST-0001") -> Device:
    return Device(
        asset_tag=asset_tag,
        type="Masaüstü",
        brand="Dell",
        model="Test",
        serial_number=f"SN-{asset_tag}",
    )


def make_user(email: str = "test.user@ornekfakulte.edu.tr") -> User:
    return User(full_name="Test Kullanıcı", email=email, role=UserRole.USER)


def test_added_device_gets_id_and_can_be_read_back(uow):
    with uow:
        device = uow.devices.add(make_device())
        uow.commit()

    assert device.id is not None
    with uow:
        loaded = uow.devices.get(device.id)
    assert loaded == device
    assert loaded.status is DeviceStatus.IN_STOCK


def test_device_can_be_found_by_asset_tag(uow):
    with uow:
        uow.devices.add(make_device("TEST-0042"))
        uow.commit()

    with uow:
        assert uow.devices.get_by_asset_tag("TEST-0042").asset_tag == "TEST-0042"
        assert uow.devices.get_by_asset_tag("YOK-0000") is None
        assert uow.devices.get_by_serial_number("SN-TEST-0042").asset_tag == "TEST-0042"
        assert uow.devices.get_by_serial_number("YOK") is None


def test_changes_are_not_persisted_without_update(uow):
    with uow:
        device = uow.devices.add(make_device())
        uow.commit()

    with uow:
        loaded = uow.devices.get(device.id)
        loaded.status = DeviceStatus.RETIRED  # update() çağrılmadı
        uow.commit()

    with uow:
        assert uow.devices.get(device.id).status is DeviceStatus.IN_STOCK


def test_update_persists_changes(uow):
    with uow:
        device = uow.devices.add(make_device())
        uow.commit()

    with uow:
        device.status = DeviceStatus.RETIRED
        device.location = "Hurda Deposu"
        uow.devices.update(device)
        uow.commit()

    with uow:
        reloaded = uow.devices.get(device.id)
    assert reloaded.status is DeviceStatus.RETIRED
    assert reloaded.location == "Hurda Deposu"


def test_active_assignment_disappears_after_return(uow):
    with uow:
        user = uow.users.add(make_user())
        device = uow.devices.add(make_device())
        assignment = uow.assignments.add(
            Assignment(device_id=device.id, user_id=user.id, assigned_by=user.id)
        )
        uow.commit()

    with uow:
        assert uow.assignments.get_active_for_device(device.id).id == assignment.id

        assignment.returned_at = datetime.now(UTC)
        uow.assignments.update(assignment)
        uow.commit()

    with uow:
        assert uow.assignments.get_active_for_device(device.id) is None


def test_ticket_modifiers_round_trip_as_enums(uow):
    with uow:
        user = uow.users.add(make_user())
        ticket = uow.tickets.add(
            Ticket(
                title="İnternet yok",
                description="Wi-Fi bağlanıyor ama sayfa açılmıyor",
                category=TicketCategory.NETWORK,
                requester_id=user.id,
                modifiers=[TicketModifier.VIP, TicketModifier.URGENT],
            )
        )
        uow.commit()

    with uow:
        loaded = uow.tickets.get(ticket.id)
    assert loaded.modifiers == [TicketModifier.VIP, TicketModifier.URGENT]
    assert all(isinstance(m, TicketModifier) for m in loaded.modifiers)


def test_get_returns_none_for_unknown_id(uow):
    with uow:
        assert uow.devices.get(999_999) is None


# --- Yalnızca gerçek veritabanına özgü davranış ---


def test_uncommitted_changes_are_rolled_back(sqlalchemy_uow):
    with sqlalchemy_uow:
        device = sqlalchemy_uow.devices.add(make_device("TEST-ROLLBACK"))
        # commit yok → with bloğundan çıkınca geri alınmalı

    with sqlalchemy_uow:
        assert sqlalchemy_uow.devices.get(device.id) is None


def test_exception_inside_block_rolls_back_everything(sqlalchemy_uow):
    with pytest.raises(RuntimeError):
        with sqlalchemy_uow:
            user = sqlalchemy_uow.users.add(make_user())
            sqlalchemy_uow.devices.add(make_device("TEST-HALF"))
            raise RuntimeError("iş kuralı ihlali")

    with sqlalchemy_uow:
        assert sqlalchemy_uow.users.get(user.id) is None
        assert sqlalchemy_uow.devices.get_by_asset_tag("TEST-HALF") is None
