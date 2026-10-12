"""Envanter modülünün varlıkları: cihaz, zimmet ve bakım kaydı."""

from dataclasses import dataclass, field
from datetime import date, datetime

from app.domain.clock import utc_now
from app.domain.enums import DeviceStatus, MaintenanceType


@dataclass(kw_only=True)
class Device:
    id: int | None = None
    asset_tag: str
    type: str
    brand: str
    model: str
    serial_number: str
    status: DeviceStatus = DeviceStatus.IN_STOCK
    location: str | None = None
    purchase_date: date | None = None


@dataclass(kw_only=True)
class Assignment:
    """Bir cihazın bir kullanıcıya zimmeti. returned_at boşsa zimmet aktiftir."""

    id: int | None = None
    device_id: int
    user_id: int
    assigned_by: int
    assigned_at: datetime = field(default_factory=utc_now)
    returned_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.returned_at is None


@dataclass(kw_only=True)
class MaintenanceRecord:
    """Cihaz bakım kaydı. completed_at boşsa bakım sürüyor demektir.

    previous_device_status, bakım bitince cihazın döneceği durumu saklar
    (iş kuralı 2: bakım kapanınca cihaz önceki durumuna döner).
    """

    id: int | None = None
    device_id: int
    technician_id: int
    ticket_id: int | None = None
    type: MaintenanceType
    description: str
    previous_device_status: DeviceStatus
    performed_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.completed_at is None
