"""Domain olayları (domain events).

Bir olay, sistemde "olmuş bir şeyi" geçmiş zamanla anlatır: DeviceAssigned,
TicketStatusChanged gibi. Olaylar değiştirilemez (frozen) — geçmiş değişmez.

Somut olaylar, onları üreten iş akışlarıyla birlikte sonraki adımlarda
(envanter, ticket) bu modüle eklenecek.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.clock import utc_now
from app.domain.enums import TicketStatus


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
class ScreenshotAttached(DomainEvent):
    ticket_id: int
    attachment_id: int
    uploaded_by: int


@dataclass(frozen=True, kw_only=True)
class TicketStatusChanged(DomainEvent):
    """Her durum geçişinde yayınlanır (atama, başlama, çözme, kapatma, yeniden açma...).

    Tek ve ortak bir olay olması, read model ve bildirim dinleyicilerinin
    her geçiş için ayrı olaya abone olmasını gereksiz kılar.
    """

    ticket_id: int
    old_status: TicketStatus
    new_status: TicketStatus
    actor_id: int | None  # None: geçişi bir kullanıcı değil sistem (AI asistan) yaptı
    assignee_id: int | None


@dataclass(frozen=True, kw_only=True)
class AiFeedbackGiven(DomainEvent):
    ticket_id: int
    ai_response_id: int
    is_helpful: bool


@dataclass(frozen=True, kw_only=True)
class AiAnswerRecorded(DomainEvent):
    ticket_id: int
    ai_response_id: int | None  # AI hiç yanıt üretemediyse None
    confidence: float | None
    escalated: bool


@dataclass(frozen=True, kw_only=True)
class TicketCommentAdded(DomainEvent):
    ticket_id: int
    comment_id: int
    author_id: int


@dataclass(frozen=True, kw_only=True)
class TicketUrgencyChanged(DomainEvent):
    ticket_id: int
    is_urgent: bool
    sla_hours: int
    priority_score: int
