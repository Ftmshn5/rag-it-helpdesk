"""Cihaz command'ları (UC-08: cihaz ekle / güncelle, hurdaya ayır).

Her command iki parçadan oluşur:
- Command: işlemin verisi (değiştirilemez dataclass). "Ne yapılmak isteniyor?"
- Handler: işlemi yürüten akış. "Nasıl yapılır?"

Handler'ın akışı her command'da aynı kalıbı izler:
  yetki kontrolü → kaydı yükle → domain metodunu çağır → kaydet → olay ekle → commit
İş kuralları domain nesnesinde (Device), akış burada.
"""

from dataclasses import dataclass
from datetime import date

from app.application.commands.common import get_device_or_raise, require_role
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.enums import UserRole
from app.domain.errors import BusinessRuleViolation
from app.domain.events import DeviceDetailsUpdated, DeviceRegistered, DeviceRetired
from app.domain.inventory import Device


@dataclass(frozen=True, kw_only=True)
class RegisterDevice:
    actor_id: int
    asset_tag: str
    type: str
    brand: str
    model: str
    serial_number: str
    location: str | None = None
    purchase_date: date | None = None


class RegisterDeviceHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: RegisterDevice) -> int:
        """Yeni cihazı depoya (IN_STOCK) kaydeder ve id'sini döndürür."""
        with self.uow:
            require_role(self.uow, command.actor_id, UserRole.ADMIN)

            if self.uow.devices.get_by_asset_tag(command.asset_tag):
                raise BusinessRuleViolation(
                    f"'{command.asset_tag}' demirbaş numarası zaten kayıtlı."
                )
            if self.uow.devices.get_by_serial_number(command.serial_number):
                raise BusinessRuleViolation(
                    f"'{command.serial_number}' seri numaralı cihaz zaten kayıtlı."
                )

            device = self.uow.devices.add(
                Device(
                    asset_tag=command.asset_tag,
                    type=command.type,
                    brand=command.brand,
                    model=command.model,
                    serial_number=command.serial_number,
                    location=command.location,
                    purchase_date=command.purchase_date,
                )
            )
            self.uow.add_event(DeviceRegistered(device_id=device.id, asset_tag=device.asset_tag))
            self.uow.commit()
            return device.id


@dataclass(frozen=True, kw_only=True)
class UpdateDeviceDetails:
    """None bırakılan alanlar değişmez."""

    actor_id: int
    device_id: int
    type: str | None = None
    brand: str | None = None
    model: str | None = None
    location: str | None = None
    purchase_date: date | None = None


class UpdateDeviceDetailsHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: UpdateDeviceDetails) -> None:
        with self.uow:
            require_role(self.uow, command.actor_id, UserRole.ADMIN)
            device = get_device_or_raise(self.uow, command.device_id)

            device.update_details(
                type=command.type,
                brand=command.brand,
                model=command.model,
                location=command.location,
                purchase_date=command.purchase_date,
            )

            self.uow.devices.update(device)
            self.uow.add_event(DeviceDetailsUpdated(device_id=device.id))
            self.uow.commit()


@dataclass(frozen=True, kw_only=True)
class RetireDevice:
    actor_id: int
    device_id: int


class RetireDeviceHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: RetireDevice) -> None:
        with self.uow:
            require_role(self.uow, command.actor_id, UserRole.ADMIN)
            device = get_device_or_raise(self.uow, command.device_id)

            device.retire()  # kural ihlalinde BusinessRuleViolation → commit olmaz

            self.uow.devices.update(device)
            self.uow.add_event(DeviceRetired(device_id=device.id))
            self.uow.commit()
