"""Cihaz command'ları (UC-08: cihaz ekle / güncelle, hurdaya ayır).

Handler'ın akışı her command'da aynı kalıbı izler:
  yetki kontrolü → kaydı yükle → domain metodunu çağır → kaydet → olay ekle → commit
İş kuralları domain nesnesinde (Device), akış burada.
"""

from dataclasses import dataclass
from datetime import date

from app.application.commands.base import ActorCommand, CommandHandler
from app.domain.enums import UserRole
from app.domain.errors import DuplicateDeviceError
from app.domain.events import DeviceDetailsUpdated, DeviceRegistered, DeviceRetired
from app.domain.inventory import Device


@dataclass(frozen=True, kw_only=True)
class RegisterDeviceCommand(ActorCommand):
    asset_tag: str
    type: str
    brand: str
    model: str
    serial_number: str
    location: str | None = None
    purchase_date: date | None = None


class RegisterDeviceHandler(CommandHandler[RegisterDeviceCommand, int]):
    def handle(self, command: RegisterDeviceCommand) -> int:
        """Yeni cihazı depoya (IN_STOCK) kaydeder ve id'sini döndürür."""
        with self._uow:
            self._require_actor(command.actor_id, UserRole.ADMIN)

            if self._uow.devices.get_by_asset_tag(command.asset_tag):
                raise DuplicateDeviceError(f"'{command.asset_tag}' demirbaş numarası zaten kayıtlı.")
            if self._uow.devices.get_by_serial_number(command.serial_number):
                raise DuplicateDeviceError(f"'{command.serial_number}' seri numaralı cihaz zaten kayıtlı.")

            device = self._uow.devices.add(
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
            self._uow.add_event(DeviceRegistered(device_id=device.id, asset_tag=device.asset_tag))
            self._uow.commit()
            return device.id


@dataclass(frozen=True, kw_only=True)
class UpdateDeviceDetailsCommand(ActorCommand):
    """None bırakılan alanlar değişmez."""

    device_id: int
    type: str | None = None
    brand: str | None = None
    model: str | None = None
    location: str | None = None
    purchase_date: date | None = None


class UpdateDeviceDetailsHandler(CommandHandler[UpdateDeviceDetailsCommand, None]):
    def handle(self, command: UpdateDeviceDetailsCommand) -> None:
        with self._uow:
            self._require_actor(command.actor_id, UserRole.ADMIN)
            device = self._get_device(command.device_id)

            device.update_details(
                type=command.type,
                brand=command.brand,
                model=command.model,
                location=command.location,
                purchase_date=command.purchase_date,
            )

            self._uow.devices.update(device)
            self._uow.add_event(DeviceDetailsUpdated(device_id=device.id))
            self._uow.commit()


@dataclass(frozen=True, kw_only=True)
class RetireDeviceCommand(ActorCommand):
    device_id: int


class RetireDeviceHandler(CommandHandler[RetireDeviceCommand, None]):
    def handle(self, command: RetireDeviceCommand) -> None:
        with self._uow:
            self._require_actor(command.actor_id, UserRole.ADMIN)
            device = self._get_device(command.device_id)

            device.retire()  # kural ihlalinde DomainError (örn. DeviceNotInStockError) → commit olmaz

            self._uow.devices.update(device)
            self._uow.add_event(DeviceRetired(device_id=device.id))
            self._uow.commit()
