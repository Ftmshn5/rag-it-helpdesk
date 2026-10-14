"""Ticket modülünün varlıkları: talep, ek, yorum ve AI yanıtı.

Davranış ekleyen decorator'lar ticket_behavior.py'de, durum geçişleri (State)
ticket_state.py'de, destek seviyeleri (Chain of Responsibility) support_tier.py'dedir.
"""

from datetime import datetime

from app.domain.clock import Clock
from app.domain.entity import Entity
from app.domain.enums import AiFeedback, SupportLevel, TicketCategory, TicketModifier, TicketStatus
from app.domain.errors import (
    AiAnswerAlreadyEvaluatedError,
    InsufficientSupportLevelError,
    InvalidAssigneeError,
    TicketClosedError,
    UrgencyChangeNotAllowedError,
)
from app.domain.support_tier import SUPPORT_CHAIN, SupportTier
from app.domain.ticket_state import STATES, TicketState
from app.domain.user import User


class Ticket(Entity):
    """Arıza kaydı. State deseni — Context: durum geçişlerini mevcut durum nesnesine sorar.

    Alanlar korumalıdır; durum, atanan teknisyen ve çözülme zamanı yalnızca
    geçiş metotlarıyla (escalate, assign_to, resolve …) değişir.
    """

    def __init__(
        self,
        *,
        id: int | None = None,
        title: str,
        description: str,
        category: TicketCategory,
        requester_id: int,
        status: TicketStatus = TicketStatus.OPEN,
        assignee_id: int | None = None,
        device_id: int | None = None,
        modifiers: list[TicketModifier] | None = None,
        support_level: SupportLevel = SupportLevel.AI,
        created_at: datetime | None = None,
        resolved_at: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self._title = title
        self._description = description
        self._category = category
        self._requester_id = requester_id
        self._status = status
        self._assignee_id = assignee_id
        self._device_id = device_id
        # Decorator nesneleri değil, yalnızca hangi decorator'ların uygulanacağı saklanır
        self._modifiers = list(modifiers or [])
        self._support_level = support_level  # her talep AI seviyesinde (L0) açılır
        self._created_at = created_at or Clock.now()
        self._resolved_at = resolved_at

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
        """Factory Method: yeni talep oluşturur; modifier'ların kaynağı burada belirlenir (iş kuralı 11).

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

    # --- Okuma ---

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def category(self) -> TicketCategory:
        return self._category

    @property
    def requester_id(self) -> int:
        return self._requester_id

    @property
    def status(self) -> TicketStatus:
        return self._status

    @property
    def assignee_id(self) -> int | None:
        return self._assignee_id

    @property
    def device_id(self) -> int | None:
        return self._device_id

    @property
    def modifiers(self) -> list[TicketModifier]:
        """Kopya döner: listeyi dışarıdan değiştirmek talebi etkilemez."""
        return list(self._modifiers)

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def resolved_at(self) -> datetime | None:
        return self._resolved_at

    @property
    def state(self) -> TicketState:
        """Veritabanındaki status alanına karşılık gelen durum nesnesi (State deseni)."""
        return STATES[self._status]

    @property
    def support_level(self) -> SupportLevel:
        return self._support_level

    @property
    def support_tier(self) -> SupportTier:
        """Talebin seviyesine karşılık gelen zincir halkası (Chain of Responsibility)."""
        return SUPPORT_CHAIN.tier(self._support_level)

    @property
    def is_urgent(self) -> bool:
        return TicketModifier.URGENT in self._modifiers

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

    def apply_ai_feedback(self, is_helpful: bool) -> None:
        """UC-02: kullanıcı AI yanıtını değerlendirir.

        - Çözüldü: kullanıcının onayı aynı zamanda çözümün onayıdır →
          AI_ANSWERED → RESOLVED → CLOSED (ayrıca "kapat" istenmez).
        - Çözülmedi: AI_ANSWERED → ESCALATED (teknisyen ataması beklenir).
        Her iki geçiş de State üzerinden yapılır; AI_ANSWERED dışında reddedilir.
        """
        if is_helpful:
            self.accept_ai_answer()
            self.close()
        else:
            self.escalate()

    # --- Durum geçişleri: kararı mevcut durum nesnesi verir, uygulamayı Ticket yapar ---

    def record_ai_answer(self) -> None:
        self._move_to(self.state.record_ai_answer())

    def accept_ai_answer(self) -> None:
        self._move_to(self.state.accept_ai_answer())

    def escalate(self) -> None:
        """Talebi bir üst destek seviyesine taşır: AI → teknisyen (iş kuralı 4, UC-02)
        veya teknisyen → kıdemli teknisyen (UC-07).

        İki desen birlikte karar verir: State bu durumda eskalasyonun mümkün olup
        olmadığını, Chain of Responsibility talebi hangi seviyenin üstleneceğini.
        İkisi de hata fırlatabilir; bu yüzden önce ikisi sorulur, sonra uygulanır
        (yarım kalmış değişiklik olmaz).
        """
        new_status = self.state.escalate()
        new_level = SUPPORT_CHAIN.escalate_from(self._support_level)
        self._move_to(new_status)
        self._support_level = new_level
        # Yeni seviyede talebi yönetici atar; eski teknisyenin sorumluluğu biter
        self._assignee_id = None

    def assign_to(self, technician: User) -> None:
        """Talebi teknisyene atar veya başka teknisyene devreder (UC-10)."""
        # İş kuralı 3: durumdan bağımsız, her atamada geçerli
        if not technician.is_technician:
            raise InvalidAssigneeError()
        new_status = self.state.assign()
        # İş kuralı 12: teknisyenin seviyesi talebin seviyesine yetmeli
        if not self.support_tier.can_be_handled_by(technician):
            raise InsufficientSupportLevelError()
        self._move_to(new_status)
        self._assignee_id = technician.id

    def start_work(self) -> None:
        self._move_to(self.state.start_work())

    def resolve(self) -> None:
        self._move_to(self.state.resolve())

    def close(self) -> None:
        self._move_to(self.state.close())

    def reopen(self) -> None:
        self._move_to(self.state.reopen())

    def _move_to(self, new_status: TicketStatus) -> None:
        """Geçişi uygular. Çözülme zamanı durum nesnesinin `is_resolved` bilgisinden türetilir:
        çözülmüş duruma ilk girişte yazılır, çözülmemiş duruma dönüşte (yeniden açma) silinir."""
        was_resolved = self.state.is_resolved
        self._status = new_status
        if self.state.is_resolved and not was_resolved:
            self._resolved_at = Clock.now()
        elif not self.state.is_resolved:
            self._resolved_at = None

    # --- Durumdan etkilenen diğer kurallar ---

    def is_participant(self, user: User) -> bool:
        """Talebin tarafları: talep sahibi, atanan teknisyen ve yönetici.

        Ek (ekran görüntüsü) yükleyebilir ve not ekleyebilirler.
        """
        return user.id in (self._requester_id, self._assignee_id) or user.is_admin

    def ensure_open_for_contributions(self) -> None:
        if not self.state.accepts_contributions:
            raise TicketClosedError()

    def set_urgent(self, is_urgent: bool) -> None:
        """Acil işaretini değiştirir (yönetici). VIP işaretine dokunmaz."""
        if not self.state.allows_urgency_change:
            raise UrgencyChangeNotAllowedError()
        if is_urgent and not self.is_urgent:
            self._modifiers.append(TicketModifier.URGENT)
        elif not is_urgent and self.is_urgent:
            self._modifiers.remove(TicketModifier.URGENT)


class TicketAttachment(Entity):
    """Talebe eklenen ekran görüntüsü. Oluşturulduktan sonra değişmez."""

    def __init__(
        self,
        *,
        id: int | None = None,
        ticket_id: int,
        file_path: str,
        mime_type: str,
        uploaded_at: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self._ticket_id = ticket_id
        self._file_path = file_path
        self._mime_type = mime_type
        self._uploaded_at = uploaded_at or Clock.now()

    @property
    def ticket_id(self) -> int:
        return self._ticket_id

    @property
    def file_path(self) -> str:
        return self._file_path

    @property
    def mime_type(self) -> str:
        return self._mime_type

    @property
    def uploaded_at(self) -> datetime:
        return self._uploaded_at


class TicketComment(Entity):
    """Talebe eklenen not. Oluşturulduktan sonra değişmez."""

    def __init__(
        self,
        *,
        id: int | None = None,
        ticket_id: int,
        author_id: int,
        content: str,
        created_at: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self._ticket_id = ticket_id
        self._author_id = author_id
        self._content = content
        self._created_at = created_at or Clock.now()

    @property
    def ticket_id(self) -> int:
        return self._ticket_id

    @property
    def author_id(self) -> int:
        return self._author_id

    @property
    def content(self) -> str:
        return self._content

    @property
    def created_at(self) -> datetime:
        return self._created_at


class AIResponse(Entity):
    """AI asistanın talebe ürettiği yanıt; yalnızca kullanıcı geri bildirimi sonradan eklenir."""

    def __init__(
        self,
        *,
        id: int | None = None,
        ticket_id: int,
        answer: str,
        confidence: float,
        sources: list[str] | None = None,
        user_feedback: AiFeedback | None = None,
    ) -> None:
        super().__init__(id)
        self._ticket_id = ticket_id
        self._answer = answer
        self._confidence = confidence
        self._sources = list(sources or [])
        self._user_feedback = user_feedback

    @property
    def ticket_id(self) -> int:
        return self._ticket_id

    @property
    def answer(self) -> str:
        return self._answer

    @property
    def confidence(self) -> float:
        return self._confidence

    @property
    def sources(self) -> list[str]:
        return list(self._sources)

    @property
    def user_feedback(self) -> AiFeedback | None:
        return self._user_feedback

    def record_feedback(self, is_helpful: bool) -> None:
        if self._user_feedback is not None:
            raise AiAnswerAlreadyEvaluatedError()
        self._user_feedback = AiFeedback.HELPFUL if is_helpful else AiFeedback.NOT_HELPFUL
