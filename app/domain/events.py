"""Domain olayları (domain events).

Bir olay, sistemde "olmuş bir şeyi" geçmiş zamanla anlatır: DeviceAssigned,
TicketStatusChanged gibi. Olaylar değiştirilemez (frozen) — geçmiş değişmez.

Somut olaylar, onları üreten iş akışlarıyla birlikte sonraki adımlarda
(envanter, ticket) bu modüle eklenecek.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.clock import utc_now


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=utc_now)


# --- Envanter ---


@dataclass(frozen=True, kw_only=True)
class DeviceRegistered(DomainEvent):
    device_id: int
    asset_tag: str


@dataclass(frozen=True, kw_only=True)
class DeviceDetailsUpdated(DomainEvent):
    device_id: int


@dataclass(frozen=True, kw_only=True)
class DeviceRetired(DomainEvent):
    device_id: int


@dataclass(frozen=True, kw_only=True)
class DeviceAssigned(DomainEvent):
    device_id: int
    user_id: int
    assignment_id: int


@dataclass(frozen=True, kw_only=True)
class DeviceReturned(DomainEvent):
    device_id: int
    user_id: int
    assignment_id: int


@dataclass(frozen=True, kw_only=True)
class MaintenanceStarted(DomainEvent):
    maintenance_record_id: int
    device_id: int
    technician_id: int


@dataclass(frozen=True, kw_only=True)
class MaintenanceCompleted(DomainEvent):
    maintenance_record_id: int
    device_id: int


# --- Ticket ---


@dataclass(frozen=True, kw_only=True)
class TicketCreated(DomainEvent):
    ticket_id: int
    requester_id: int
    # Decorator'lı nesneden hesaplanan değerler; dinleyiciler (bildirim, read
    # model) Factory'yi yeniden çalıştırmadan kullanabilir.
    sla_hours: int
    priority_score: int


@dataclass(frozen=True, kw_only=True)
class TicketUrgencyChanged(DomainEvent):
    ticket_id: int
    is_urgent: bool
    sla_hours: int
    priority_score: int
