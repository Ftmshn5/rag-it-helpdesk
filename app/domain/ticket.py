"""Ticket modülünün varlıkları: talep, ek, yorum ve AI yanıtı.

Davranış ekleyen decorator'lar ticket_behavior.py'de; durum geçişleri (State)
sonraki adımda eklenecek.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.clock import utc_now
from app.domain.enums import AiFeedback, TicketCategory, TicketModifier, TicketStatus, UserRole
from app.domain.errors import BusinessRuleViolation
from app.domain.user import User

FINISHED_STATUSES = {TicketStatus.RESOLVED, TicketStatus.CLOSED}


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

    @classmethod
    def open(
        cls,
        *,
        requester: User,
        title: str,
        description: str,
        category: TicketCategory,
        is_urgent: bool = False,
        device_id: int | None = None,
    ) -> "Ticket":
        """Yeni talep oluşturur; modifier'ların kaynağı burada belirlenir.

        - VIP: talep sahibinin is_vip alanından otomatik gelir (kullanıcı seçemez).
        - URGENT: kullanıcı talep açarken işaretler.
        """
        modifiers = []
        if requester.is_vip:
            modifiers.append(TicketModifier.VIP)
        if is_urgent:
            modifiers.append(TicketModifier.URGENT)
        return cls(
            title=title,
            description=description,
            category=category,
            requester_id=requester.id,
            device_id=device_id,
            modifiers=modifiers,
        )

    @property
    def is_urgent(self) -> bool:
        return TicketModifier.URGENT in self.modifiers

    def can_receive_attachment_from(self, user: User) -> bool:
        """Talep sahibi, atanan teknisyen ve yönetici ek yükleyebilir."""
        return user.id in (self.requester_id, self.assignee_id) or user.role == UserRole.ADMIN

    def ensure_accepts_attachments(self) -> None:
        if self.status == TicketStatus.CLOSED:
            raise BusinessRuleViolation("Kapanmış talebe ek eklenemez.")

    def set_urgent(self, is_urgent: bool) -> None:
        """Acil işaretini değiştirir (yönetici). VIP işaretine dokunmaz."""
        if self.status in FINISHED_STATUSES:
            raise BusinessRuleViolation("Çözülmüş veya kapanmış talebin aciliyeti değiştirilemez.")
        if is_urgent and not self.is_urgent:
            self.modifiers.append(TicketModifier.URGENT)
        elif not is_urgent and self.is_urgent:
            self.modifiers.remove(TicketModifier.URGENT)


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
