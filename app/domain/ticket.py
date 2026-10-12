"""Ticket modülünün varlıkları: talep, ek, yorum ve AI yanıtı.

Davranış ekleyen decorator'lar ticket_behavior.py'de, durum geçişleri (State)
ticket_state.py'dedir.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.clock import utc_now
from app.domain.enums import AiFeedback, TicketCategory, TicketModifier, TicketStatus, UserRole
from app.domain.errors import BusinessRuleViolation
from app.domain.ticket_state import STATES, TicketState
from app.domain.user import User


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
    def state(self) -> TicketState:
        """Veritabanındaki status alanına karşılık gelen durum nesnesi (State deseni)."""
        return STATES[self.status]

    @property
    def is_urgent(self) -> bool:
        return TicketModifier.URGENT in self.modifiers

    # --- İş kuralı 4 ---

    def receive_ai_answer(self, confidence: float | None, threshold: float) -> bool:
        """AI sonucunu uygular; yanıt kullanıcıya sunulacaksa True döner.

        Güven eşiğin altındaysa (veya AI hiç yanıt üretemediyse: None) talep
        AI yanıtı gösterilmeden doğrudan eskale edilir.
        """
        if confidence is not None and confidence >= threshold:
            self.record_ai_answer()
            return True
        self.escalate()
        return False

    # --- Durum geçişleri: kararı mevcut durum nesnesi verir ---

    def record_ai_answer(self) -> None:
        self.state.record_ai_answer(self)

    def accept_ai_answer(self) -> None:
        self.state.accept_ai_answer(self)

    def escalate(self) -> None:
        self.state.escalate(self)

    def assign(self, technician: User) -> None:
        # İş kuralı 3: durumdan bağımsız, her atamada geçerli
        if not technician.is_technician:
            raise BusinessRuleViolation("Talep yalnızca teknisyen rolündeki kullanıcıya atanabilir.")
        self.state.assign(self, technician.id)

    def start_work(self) -> None:
        self.state.start_work(self)

    def resolve(self) -> None:
        self.state.resolve(self)

    def close(self) -> None:
        self.state.close(self)

    def reopen(self) -> None:
        self.state.reopen(self)

    # --- Durumdan etkilenen diğer kurallar ---

    def is_participant(self, user: User) -> bool:
        """Talebin tarafları: talep sahibi, atanan teknisyen ve yönetici.

        Ek (ekran görüntüsü) yükleyebilir ve not ekleyebilirler.
        """
        return user.id in (self.requester_id, self.assignee_id) or user.role == UserRole.ADMIN

    def ensure_open_for_contributions(self) -> None:
        if not self.state.accepts_contributions:
            raise BusinessRuleViolation("Kapanmış talebe ek veya not eklenemez.")

    def set_urgent(self, is_urgent: bool) -> None:
        """Acil işaretini değiştirir (yönetici). VIP işaretine dokunmaz."""
        if not self.state.allows_urgency_change:
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
