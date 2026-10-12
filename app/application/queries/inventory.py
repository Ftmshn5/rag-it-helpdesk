"""Envanter sorguları (CQRS okuma tarafı).

UC-11 envanter raporu ve UC-04 zimmetli cihazlarım read.device_inventory'den;
UC-17 bakım geçmişi doğrudan write tablosundan (tek tablo, projeksiyon gereksiz).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime

from app.application.errors import NotFoundError
from app.application.queries.users import UserQueries, require_viewer
from app.domain.enums import DeviceStatus, MaintenanceType, UserRole

# --- DTO'lar ---


@dataclass(frozen=True)
class DeviceInventoryView:
    device_id: int
    asset_tag: str
    type: str
    brand: str
    model: str
    serial_number: str
    status: DeviceStatus
    location: str | None
    purchase_date: date | None
    holder_id: int | None
    holder_name: str | None
    holder_department: str | None
    assigned_at: datetime | None
    has_open_maintenance: bool
    maintenance_count: int
    last_maintenance_at: datetime | None


@dataclass(frozen=True)
class InventoryReportView:
    total: int
    by_status: dict[DeviceStatus, int]
    by_type: dict[str, int]
    devices: list[DeviceInventoryView] = field(default_factory=list)


@dataclass(frozen=True)
class MaintenanceRecordView:
    id: int
    type: MaintenanceType
    description: str
    technician_id: int
    technician_name: str
    ticket_id: int | None
    performed_at: datetime
    completed_at: datetime | None
    is_open: bool


# --- Okuma arayüzü ---


class InventoryQueries(ABC):
    @abstractmethod
    def list_devices(
        self, status: DeviceStatus | None = None, device_type: str | None = None
    ) -> list[DeviceInventoryView]: ...

    @abstractmethod
    def list_held_by(self, user_id: int) -> list[DeviceInventoryView]: ...

    @abstractmethod
    def device_exists(self, device_id: int) -> bool: ...

    @abstractmethod
    def maintenance_history(self, device_id: int) -> list[MaintenanceRecordView]:
        """En yeni bakım önce."""


# --- Sorgu handler'ları ---


class GetInventoryReportHandler:
    """UC-11: yönetici envanter raporu (filtrelenebilir liste + durum/tür sayıları)."""

    def __init__(self, inventory: InventoryQueries, users: UserQueries) -> None:
        self.inventory, self.users = inventory, users

    def handle(
        self, actor_id: int, status: DeviceStatus | None = None, device_type: str | None = None
    ) -> InventoryReportView:
        require_viewer(self.users, actor_id, UserRole.ADMIN)
        devices = self.inventory.list_devices(status, device_type)

        by_status = {s: 0 for s in DeviceStatus}  # sıfır olan durumlar da raporda görünsün
        by_type: dict[str, int] = {}
        for device in devices:
            by_status[device.status] += 1
            by_type[device.type] = by_type.get(device.type, 0) + 1

        return InventoryReportView(
            total=len(devices), by_status=by_status, by_type=by_type, devices=devices
        )


class ListMyDevicesHandler:
    """UC-04: kullanıcı kendisine zimmetli cihazları görür."""

    def __init__(self, inventory: InventoryQueries, users: UserQueries) -> None:
        self.inventory, self.users = inventory, users

    def handle(self, actor_id: int) -> list[DeviceInventoryView]:
        actor = require_viewer(self.users, actor_id)
        return self.inventory.list_held_by(actor.id)


class GetMaintenanceHistoryHandler:
    """UC-17: teknisyen ve yönetici bir cihazın bakım geçmişini görür."""

    def __init__(self, inventory: InventoryQueries, users: UserQueries) -> None:
        self.inventory, self.users = inventory, users

    def handle(self, actor_id: int, device_id: int) -> list[MaintenanceRecordView]:
        require_viewer(self.users, actor_id, UserRole.TECHNICIAN, UserRole.ADMIN)
        if not self.inventory.device_exists(device_id):
            raise NotFoundError("Cihaz bulunamadı.")
        return self.inventory.maintenance_history(device_id)
