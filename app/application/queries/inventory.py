"""Envanter sorguları (CQRS okuma tarafı).

UC-11 envanter raporu, UC-04 zimmetli cihazlarım ve cihaz detayı (E5, QR) read.device_inventory'den;
UC-17 bakım geçmişi doğrudan write tablosundan (tek tablo, projeksiyon gereksiz).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import date, datetime

from app.application.errors import NotFoundError
from app.application.queries.base import ActorQuery, QueryHandler, TQuery, TResult
from app.application.queries.users import UserQueries
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
    def get_device(self, device_id: int) -> DeviceInventoryView | None: ...

    @abstractmethod
    def device_exists(self, device_id: int) -> bool: ...

    @abstractmethod
    def maintenance_history(self, device_id: int) -> list[MaintenanceRecordView]:
        """En yeni bakım önce."""


# --- Sorgular ---


@dataclass(frozen=True, kw_only=True)
class GetInventoryReportQuery(ActorQuery):
    status: DeviceStatus | None = None
    device_type: str | None = None


@dataclass(frozen=True, kw_only=True)
class ListDevicesQuery(ActorQuery):
    status: DeviceStatus | None = None
    device_type: str | None = None


@dataclass(frozen=True, kw_only=True)
class ListMyDevicesQuery(ActorQuery):
    pass


@dataclass(frozen=True, kw_only=True)
class GetMaintenanceHistoryQuery(ActorQuery):
    device_id: int


@dataclass(frozen=True, kw_only=True)
class GetDeviceQuery(ActorQuery):
    device_id: int


# --- Sorgu handler'ları ---


class InventoryQueryHandler(QueryHandler[TQuery, TResult]):
    """Envanter sorgularının ortak tabanı: envanter okuma arayüzünü de alır."""

    def __init__(self, inventory: InventoryQueries, users: UserQueries) -> None:
        super().__init__(users)
        self._inventory = inventory


class GetInventoryReportHandler(InventoryQueryHandler[GetInventoryReportQuery, InventoryReportView]):
    """UC-11: yönetici envanter raporu (filtrelenebilir liste + durum/tür sayıları)."""

    def handle(self, query: GetInventoryReportQuery) -> InventoryReportView:
        self._require_viewer(query.actor_id, UserRole.ADMIN)
        devices = self._inventory.list_devices(query.status, query.device_type)

        by_status = {s: 0 for s in DeviceStatus}  # sıfır olan durumlar da raporda görünsün
        by_type: dict[str, int] = {}
        for device in devices:
            by_status[device.status] += 1
            by_type[device.type] = by_type.get(device.type, 0) + 1

        return InventoryReportView(total=len(devices), by_status=by_status, by_type=by_type, devices=devices)


class ListDevicesHandler(InventoryQueryHandler[ListDevicesQuery, list[DeviceInventoryView]]):
    """Cihaz listesi: teknisyen bakım kaydı açmak, yönetici zimmet işlemleri için kullanır.

    Envanter raporundan (yalnızca yönetici) farkı: sayımlar yok, yalnızca liste.
    """

    def handle(self, query: ListDevicesQuery) -> list[DeviceInventoryView]:
        self._require_viewer(query.actor_id, UserRole.TECHNICIAN, UserRole.ADMIN)
        return self._inventory.list_devices(query.status, query.device_type)


class ListMyDevicesHandler(InventoryQueryHandler[ListMyDevicesQuery, list[DeviceInventoryView]]):
    """UC-04: kullanıcı kendisine zimmetli cihazları görür."""

    def handle(self, query: ListMyDevicesQuery) -> list[DeviceInventoryView]:
        actor = self._require_viewer(query.actor_id)
        return self._inventory.list_held_by(actor.id)


class GetMaintenanceHistoryHandler(InventoryQueryHandler[GetMaintenanceHistoryQuery, list[MaintenanceRecordView]]):
    """UC-17: teknisyen ve yönetici bir cihazın bakım geçmişini görür."""

    def handle(self, query: GetMaintenanceHistoryQuery) -> list[MaintenanceRecordView]:
        self._require_viewer(query.actor_id, UserRole.TECHNICIAN, UserRole.ADMIN)
        if not self._inventory.device_exists(query.device_id):
            raise NotFoundError("Cihaz bulunamadı.")
        return self._inventory.maintenance_history(query.device_id)


class GetDeviceHandler(InventoryQueryHandler[GetDeviceQuery, DeviceInventoryView]):
    """E5: cihaz detayı (cihazın QR etiketi okutulunca açılan sayfa). Her rol görebilir.

    Zimmet sahibi kişisel bilgidir: yalnızca personel (teknisyen, yönetici) ve cihazın
    kendi sahibi görür. Örneğin laboratuvardaki bir bilgisayarı okutan öğrenci, cihazın
    durumunu ve konumunu görür ama kime zimmetli olduğunu görmez.
    """

    def handle(self, query: GetDeviceQuery) -> DeviceInventoryView:
        viewer = self._require_viewer(query.actor_id)
        device = self._inventory.get_device(query.device_id)
        if device is None:
            raise NotFoundError("Cihaz bulunamadı.")

        is_staff = viewer.role in (UserRole.TECHNICIAN, UserRole.ADMIN)
        if is_staff or device.holder_id == viewer.id:
            return device
        return replace(device, holder_id=None, holder_name=None, holder_department=None, assigned_at=None)
