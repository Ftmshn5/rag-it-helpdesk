"""Ticket yaşam döngüsü: State deseni.

Ticket'ın durumuna göre hangi işlemlerin yapılabileceği değişir. Bunu
`if status == ... elif ...` bloklarıyla her metoda dağıtmak yerine, her durum
kendi sınıfında yalnızca kendisinden mümkün olan geçişleri tanımlar:

    OPEN         → AI_ANSWERED (AI yanıt verdi)  | ESCALATED (düşük güven)
    AI_ANSWERED  → RESOLVED (kullanıcı: çözüldü) | ESCALATED (kullanıcı: çözülmedi)
    ESCALATED    → ASSIGNED (teknisyene atandı)
    ASSIGNED     → IN_PROGRESS (çalışmaya başlandı) | ASSIGNED (başkasına atandı)
    IN_PROGRESS  → RESOLVED (teknisyen çözdü)       | ASSIGNED (başkasına atandı)
    RESOLVED     → CLOSED (çözüm onaylandı)         | ESCALATED (yeniden açıldı)
    CLOSED       → (son durum)

Taban sınıftaki her işlem varsayılan olarak "bu durumda yapılamaz" hatası
verir; bir durum sınıfı yalnızca izin verdiği işlemleri ezer. Yeni bir geçiş
eklemek, ilgili durum sınıfına tek bir metot eklemek demektir.

Context, Ticket nesnesidir: veritabanında yalnızca `status` alanı saklanır,
`ticket.state` bu alandan ilgili durum nesnesini bulur. Durum sınıfları veri
tutmadığı için her durumdan tek bir nesne yeterlidir.
"""

from abc import ABC
from typing import TYPE_CHECKING

from app.domain.clock import utc_now
from app.domain.enums import TicketStatus
from app.domain.errors import BusinessRuleViolation

if TYPE_CHECKING:
    from app.domain.ticket import Ticket

STATUS_LABELS = {
    TicketStatus.OPEN: "Açık",
    TicketStatus.AI_ANSWERED: "AI yanıtladı",
    TicketStatus.ESCALATED: "Eskale edildi",
    TicketStatus.ASSIGNED: "Atandı",
    TicketStatus.IN_PROGRESS: "Üzerinde çalışılıyor",
    TicketStatus.RESOLVED: "Çözüldü",
    TicketStatus.CLOSED: "Kapandı",
}


class TicketState(ABC):
    status: TicketStatus
    accepts_contributions = True
    allows_urgency_change = True

    def _not_allowed(self, action: str) -> BusinessRuleViolation:
        return BusinessRuleViolation(
            f"'{STATUS_LABELS[self.status]}' durumundaki talep için {action} yapılamaz."
        )

    # --- Geçişler: varsayılan olarak hepsi yasak ---

    def record_ai_answer(self, ticket: "Ticket") -> None:
        raise self._not_allowed("AI yanıtı kaydı")

    def accept_ai_answer(self, ticket: "Ticket") -> None:
        raise self._not_allowed("AI yanıtını onaylama")

    def escalate(self, ticket: "Ticket") -> None:
        raise self._not_allowed("eskalasyon")

    def assign(self, ticket: "Ticket", technician_id: int) -> None:
        raise self._not_allowed("teknisyen ataması")

    def start_work(self, ticket: "Ticket") -> None:
        raise self._not_allowed("çalışmaya başlama")

    def resolve(self, ticket: "Ticket") -> None:
        raise self._not_allowed("çözüldü olarak işaretleme")

    def close(self, ticket: "Ticket") -> None:
        raise self._not_allowed("kapatma")

    def reopen(self, ticket: "Ticket") -> None:
        raise self._not_allowed("yeniden açma")


# --- Ortak geçiş yardımcıları ---


def _mark_resolved(ticket: "Ticket") -> None:
    ticket.status = TicketStatus.RESOLVED
    ticket.resolved_at = utc_now()


def _assign(ticket: "Ticket", technician_id: int) -> None:
    ticket.assignee_id = technician_id
    ticket.status = TicketStatus.ASSIGNED


# --- Somut durumlar ---


class OpenState(TicketState):
    status = TicketStatus.OPEN

    def record_ai_answer(self, ticket: "Ticket") -> None:
        ticket.status = TicketStatus.AI_ANSWERED

    def escalate(self, ticket: "Ticket") -> None:
        # İş kuralı 4: AI güveni eşiğin altındaysa AI yanıtı gösterilmeden eskale edilir
        ticket.status = TicketStatus.ESCALATED


class AiAnsweredState(TicketState):
    status = TicketStatus.AI_ANSWERED

    def accept_ai_answer(self, ticket: "Ticket") -> None:
        _mark_resolved(ticket)

    def escalate(self, ticket: "Ticket") -> None:
        ticket.status = TicketStatus.ESCALATED


class EscalatedState(TicketState):
    status = TicketStatus.ESCALATED

    def assign(self, ticket: "Ticket", technician_id: int) -> None:
        _assign(ticket, technician_id)


class AssignedState(TicketState):
    status = TicketStatus.ASSIGNED

    def assign(self, ticket: "Ticket", technician_id: int) -> None:
        _assign(ticket, technician_id)  # başka bir teknisyene devir

    def start_work(self, ticket: "Ticket") -> None:
        ticket.status = TicketStatus.IN_PROGRESS


class InProgressState(TicketState):
    status = TicketStatus.IN_PROGRESS

    def assign(self, ticket: "Ticket", technician_id: int) -> None:
        _assign(ticket, technician_id)  # devredilen teknisyen işe yeniden başlar

    def resolve(self, ticket: "Ticket") -> None:
        _mark_resolved(ticket)


class ResolvedState(TicketState):
    status = TicketStatus.RESOLVED
    allows_urgency_change = False

    def close(self, ticket: "Ticket") -> None:
        ticket.status = TicketStatus.CLOSED

    def reopen(self, ticket: "Ticket") -> None:
        # Sorun sürüyor: yeniden teknisyen ataması için eskalasyon kuyruğuna döner.
        # Önceki teknisyen bilgisi korunur; yönetici aynı kişiye tekrar atayabilir.
        ticket.status = TicketStatus.ESCALATED
        ticket.resolved_at = None


class ClosedState(TicketState):
    status = TicketStatus.CLOSED
    accepts_contributions = False
    allows_urgency_change = False


STATES: dict[TicketStatus, TicketState] = {
    state.status: state
    for state in (
        OpenState(),
        AiAnsweredState(),
        EscalatedState(),
        AssignedState(),
        InProgressState(),
        ResolvedState(),
        ClosedState(),
    )
}
