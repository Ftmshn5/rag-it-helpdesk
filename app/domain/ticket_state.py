"""Ticket yaşam döngüsü: State deseni.

Ticket'ın durumuna göre hangi işlemlerin yapılabileceği değişir. Bunu
`if status == ... elif ...` bloklarıyla her metoda dağıtmak yerine, her durum
kendi sınıfında yalnızca kendisinden mümkün olan geçişleri tanımlar:

    OPEN         → AI_ANSWERED (AI yanıt verdi)  | ESCALATED (düşük güven)
    AI_ANSWERED  → RESOLVED (kullanıcı: çözüldü) | ESCALATED (kullanıcı: çözülmedi)
    ESCALATED    → ASSIGNED (teknisyene atandı)
    ASSIGNED     → IN_PROGRESS (çalışmaya başlandı) | ASSIGNED (başkasına atandı) | ESCALATED (üst seviyeye)
    IN_PROGRESS  → RESOLVED (teknisyen çözdü)       | ASSIGNED (başkasına atandı) | ESCALATED (üst seviyeye)
    RESOLVED     → CLOSED (çözüm onaylandı)         | ESCALATED (yeniden açıldı)
    CLOSED       → (son durum)

Taban sınıftaki her işlem varsayılan olarak "bu durumda yapılamaz" hatası
verir; bir durum sınıfı yalnızca izin verdiği işlemleri ezer (çok biçimlilik).
Yeni bir geçiş eklemek, ilgili durum sınıfına tek bir metot eklemek demektir.

Her durum ayrıca kendisine girilince kime haber verileceğini bilir
(`entry_notifications`): örneğin ASSIGNED'a girilince atanan teknisyene ve talep
sahibine bildirim gider. Bildirimi gönderen kod hangi durumda ne söyleneceğini
bilmez; yeni durumun nesnesine sorar (çok biçimlilik, if/elif yok).

Durum nesneleri yalnızca karar verir: geçiş izinliyse bir sonraki durumu
döndürür. Değişikliği Context (Ticket) kendisi uygular; böylece Ticket'ın
alanlarına dışarıdan dokunulmaz (kapsülleme). Durum sınıfları veri tutmadığı
için her durumdan tek bir nesne yeterlidir.
"""

from abc import ABC

from app.domain.enums import TicketStatus
from app.domain.errors import InvalidTicketTransitionError
from app.domain.notifications import Notification, NotificationAudience, NotificationChannel

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
    """State deseni — State: talebin bir durumundaki davranış.

    Her geçiş metodu izinliyse hedef durumu döndürür; izinli değilse
    InvalidTicketTransitionError fırlatır (varsayılan).
    """

    status: TicketStatus
    accepts_contributions = True  # ek ve not eklenebilir mi
    allows_urgency_change = True  # aciliyet değiştirilebilir mi
    is_resolved = False  # çözülmüş sayılır mı (resolved_at dolu olmalı mı)

    def entry_notifications(self, title: str) -> list[Notification]:
        """Talep bu duruma girince gönderilecek bildirimler (varsayılan: yok)."""
        return []

    @staticmethod
    def _in_app(audience: NotificationAudience, message: str) -> Notification:
        return Notification(NotificationChannel.IN_APP, audience, message)

    def _not_allowed(self, action: str) -> InvalidTicketTransitionError:
        return InvalidTicketTransitionError(f"'{STATUS_LABELS[self.status]}' durumundaki talep için {action} yapılamaz.")

    # --- Geçişler: varsayılan olarak hepsi yasak ---

    def record_ai_answer(self) -> TicketStatus:
        raise self._not_allowed("AI yanıtı kaydı")

    def accept_ai_answer(self) -> TicketStatus:
        raise self._not_allowed("AI yanıtını onaylama")

    def escalate(self) -> TicketStatus:
        raise self._not_allowed("eskalasyon")

    def assign(self) -> TicketStatus:
        raise self._not_allowed("teknisyen ataması")

    def start_work(self) -> TicketStatus:
        raise self._not_allowed("çalışmaya başlama")

    def resolve(self) -> TicketStatus:
        raise self._not_allowed("çözüldü olarak işaretleme")

    def close(self) -> TicketStatus:
        raise self._not_allowed("kapatma")

    def reopen(self) -> TicketStatus:
        raise self._not_allowed("yeniden açma")


# --- Somut durumlar (State deseni — Concrete State) ---


class OpenState(TicketState):
    """State deseni — Concrete State: yeni açılmış talep; AI yanıtı bekleniyor."""

    status = TicketStatus.OPEN

    def record_ai_answer(self) -> TicketStatus:
        return TicketStatus.AI_ANSWERED

    def escalate(self) -> TicketStatus:
        # İş kuralı 4: AI güveni eşiğin altındaysa AI yanıtı gösterilmeden eskale edilir
        return TicketStatus.ESCALATED


class AiAnsweredState(TicketState):
    """State deseni — Concrete State: AI önerisi kullanıcının değerlendirmesini bekliyor."""

    status = TicketStatus.AI_ANSWERED

    def entry_notifications(self, title: str) -> list[Notification]:
        return [
            self._in_app(NotificationAudience.REQUESTER, f"AI asistan bir çözüm önerdi, lütfen değerlendirin: {title}")
        ]

    def accept_ai_answer(self) -> TicketStatus:
        return TicketStatus.RESOLVED

    def escalate(self) -> TicketStatus:
        return TicketStatus.ESCALATED


class EscalatedState(TicketState):
    """State deseni — Concrete State: teknisyen ataması bekleniyor."""

    status = TicketStatus.ESCALATED

    def entry_notifications(self, title: str) -> list[Notification]:
        return [self._in_app(NotificationAudience.IT_MANAGERS, f"Talep teknisyen ataması bekliyor: {title}")]

    def assign(self) -> TicketStatus:
        return TicketStatus.ASSIGNED


class AssignedState(TicketState):
    """State deseni — Concrete State: teknisyene atandı, çalışma başlamadı."""

    status = TicketStatus.ASSIGNED

    def entry_notifications(self, title: str) -> list[Notification]:
        return [
            self._in_app(NotificationAudience.ASSIGNEE, f"Size bir talep atandı: {title}"),
            self._in_app(NotificationAudience.REQUESTER, f"Talebiniz bir teknisyene atandı: {title}"),
        ]

    def assign(self) -> TicketStatus:
        return TicketStatus.ASSIGNED  # başka bir teknisyene devir

    def start_work(self) -> TicketStatus:
        return TicketStatus.IN_PROGRESS

    def escalate(self) -> TicketStatus:
        return TicketStatus.ESCALATED  # UC-07: üst seviyeye (hangi seviye: SupportChain)


class InProgressState(TicketState):
    """State deseni — Concrete State: teknisyen üzerinde çalışıyor."""

    status = TicketStatus.IN_PROGRESS

    def entry_notifications(self, title: str) -> list[Notification]:
        return [self._in_app(NotificationAudience.REQUESTER, f"Talebiniz üzerinde çalışılıyor: {title}")]

    def assign(self) -> TicketStatus:
        return TicketStatus.ASSIGNED  # devredilen teknisyen işe yeniden başlar

    def resolve(self) -> TicketStatus:
        return TicketStatus.RESOLVED

    def escalate(self) -> TicketStatus:
        return TicketStatus.ESCALATED  # UC-07: üst seviyeye (hangi seviye: SupportChain)


class ResolvedState(TicketState):
    """State deseni — Concrete State: çözüldü; talep sahibinin onayı bekleniyor."""

    status = TicketStatus.RESOLVED
    allows_urgency_change = False
    is_resolved = True

    def entry_notifications(self, title: str) -> list[Notification]:
        return [
            self._in_app(NotificationAudience.REQUESTER, f"Talebiniz çözüldü, lütfen çözümü onaylayın: {title}")
        ]

    def close(self) -> TicketStatus:
        return TicketStatus.CLOSED

    def reopen(self) -> TicketStatus:
        # Sorun sürüyor: yeniden teknisyen ataması için eskalasyon kuyruğuna döner.
        # Önceki teknisyen bilgisi korunur; yönetici aynı kişiye tekrar atayabilir.
        return TicketStatus.ESCALATED


class ClosedState(TicketState):
    """State deseni — Concrete State: son durum; hiçbir geçiş, ek veya aciliyet değişikliği yok."""

    status = TicketStatus.CLOSED
    accepts_contributions = False
    allows_urgency_change = False
    is_resolved = True


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
