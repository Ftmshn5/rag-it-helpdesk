"""Ticket modülünün varlıkları: talep, ek, yorum ve AI yanıtı.

Durum geçişleri (State) ve davranış ekleyen decorator'lar sonraki adımlarda
bu modülün yanına eklenecek.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.clock import utc_now
from app.domain.enums import AiFeedback, TicketCategory, TicketModifier, TicketStatus


@dataclass(kw_only=True)
class Ticket:
    id: int | None = None
    title: str
    description: str
    category: TicketCategory
    status: TicketStatus = TicketStatus.OPEN
    requester_id: int
    assignee_id: int | None = None
    device_id: int | None = None
    # Decorator nesneleri değil, yalnızca hangi decorator'ların uygulanacağı saklanır
    modifiers: list[TicketModifier] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    resolved_at: datetime | None = None


@dataclass(kw_only=True)
class TicketAttachment:
    id: int | None = None
    ticket_id: int
    file_path: str
    mime_type: str
    uploaded_at: datetime = field(default_factory=utc_now)


@dataclass(kw_only=True)
class TicketComment:
    id: int | None = None
    ticket_id: int
    author_id: int
    content: str
    created_at: datetime = field(default_factory=utc_now)


@dataclass(kw_only=True)
class AIResponse:
    id: int | None = None
    ticket_id: int
    answer: str
    confidence: float
    sources: list[str] = field(default_factory=list)
    user_feedback: AiFeedback | None = None
