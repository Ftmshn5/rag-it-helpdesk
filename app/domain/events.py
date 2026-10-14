"""Domain olayları (domain events).

Bir olay, sistemde "olmuş bir şeyi" geçmiş zamanla anlatır: DeviceAssigned,
TicketStatusChanged gibi. Olaylar değiştirilemez (frozen) — geçmiş değişmez.

Hiyerarşi (kalıtım): DomainEvent → DeviceEvent (device_id taşır) / TicketEvent
(ticket_id taşır) → somut olaylar. Dinleyiciler ortak alana ara taban üzerinden
güvenle erişir (örn. read model projektörleri).
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.clock import Clock
from app.domain.enums import TicketStatus


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=Clock.now)


@dataclass(frozen=True, kw_only=True)
class DeviceEvent(DomainEvent):
    """Bir cihazı etkileyen olayların ortak tabanı."""

    device_id: int


@dataclass(frozen=True, kw_only=True)
class TicketEvent(DomainEvent):
    """Bir talebi etkileyen olayların ortak tabanı."""

    ticket_id: int


# --- Envanter ---


@dataclass(frozen=True, kw_only=True)
class DeviceRegistered(DeviceEvent):
    asset_tag: str


@dataclass(frozen=True, kw_only=True)
class DeviceDetailsUpdated(DeviceEvent):
    """Cihazın tanımlayıcı olmayan bilgileri değişti (tür, marka, konum…)."""


@dataclass(frozen=True, kw_only=True)
class DeviceRetired(DeviceEvent):
    """Cihaz hurdaya ayrıldı."""


@dataclass(frozen=True, kw_only=True)
class DeviceAssigned(DeviceEvent):
    user_id: int
    assignment_id: int


@dataclass(frozen=True, kw_only=True)
class DeviceReturned(DeviceEvent):
    user_id: int
    assignment_id: int


@dataclass(frozen=True, kw_only=True)
class MaintenanceStarted(DeviceEvent):
    maintenance_record_id: int
    technician_id: int


@dataclass(frozen=True, kw_only=True)
class MaintenanceCompleted(DeviceEvent):
    maintenance_record_id: int


# --- Ticket ---


@dataclass(frozen=True, kw_only=True)
class TicketCreated(TicketEvent):
    requester_id: int
    # Decorator'lı nesneden hesaplanan değerler; dinleyiciler (bildirim, read
    # model) Factory'yi yeniden çalıştırmadan kullanabilir.
    sla_hours: int
    priority_score: int


@dataclass(frozen=True, kw_only=True)
class ScreenshotAttached(TicketEvent):
    attachment_id: int
    uploaded_by: int


@dataclass(frozen=True, kw_only=True)
class TicketStatusChanged(TicketEvent):
    """Her durum geçişinde yayınlanır (atama, başlama, çözme, kapatma, yeniden açma...).

    Tek ve ortak bir olay olması, read model ve bildirim dinleyicilerinin
    her geçiş için ayrı olaya abone olmasını gereksiz kılar.
    """

    old_status: TicketStatus
    new_status: TicketStatus
    actor_id: int | None  # None: geçişi bir kullanıcı değil sistem (AI asistan) yaptı
    assignee_id: int | None


@dataclass(frozen=True, kw_only=True)
class AiFeedbackGiven(TicketEvent):
    ai_response_id: int
    is_helpful: bool


@dataclass(frozen=True, kw_only=True)
class AiAnswerRecorded(TicketEvent):
    ai_response_id: int | None  # AI hiç yanıt üretemediyse None
    confidence: float | None
    escalated: bool


@dataclass(frozen=True, kw_only=True)
class TicketCommentAdded(TicketEvent):
    comment_id: int
    author_id: int


@dataclass(frozen=True, kw_only=True)
class TicketUrgencyChanged(TicketEvent):
    is_urgent: bool
    sla_hours: int
    priority_score: int
    actor_id: int | None = None  # değişikliği yapan yönetici (zaman çizelgesi için)
