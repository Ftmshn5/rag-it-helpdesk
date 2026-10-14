"""Ticket davranışları: Decorator ve Factory desenleri.

DECORATOR
---------
Ticket'a çalışma anında, alt sınıf patlaması olmadan davranış ekler. VIP ve Acil
bağımsız özellikler; kalıtımla yapılsaydı VipTicket, UrgentTicket ve
VipUrgentTicket gibi her kombinasyon için ayrı sınıf gerekirdi. Decorator'da her
özellik tek bir sarmalayıcıdır ve istenen sırayla üst üste giydirilir:

    UrgentTicket(VipTicket(BasicTicket(ticket)))

Her sarmalayıcı aynı arayüzü (TicketComponent) uygular, işi içteki nesneye
devreder ve sonucu kendi kuralıyla değiştirir:

    sla_hours():       72 → VIP: en geç 24 → Acil: en geç 4
    priority_score():  10 → VIP: +20       → Acil: +50
    layers():          her katman kendi etkisini rapor eder (arayüzde SLA açıklaması)
    notify():          [teknisyenler] → + [BT yöneticisi e-posta] → + [nöbetçi teknisyen SMS]

FACTORY
-------
Veritabanında decorator nesnesi saklanmaz, yalnızca `ticket.modifiers` listesi
(örn. ["VIP", "URGENT"]) tutulur. TicketComponentFactory bu listeye bakarak
doğru sarmalayıcıları doğru sırada giydirir; ticket'ı kullanan kod hangi
decorator'ların uygulandığını bilmek zorunda kalmaz.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.enums import TicketModifier
from app.domain.notifications import Notification, NotificationAudience, NotificationChannel
from app.domain.ticket import Ticket


@dataclass(frozen=True)
class BehaviorLayer:
    """Zincirin bir katmanı uygulandıktan sonraki SLA ve öncelik (değer nesnesi).

    Arayüzde "SLA nasıl oluştu" açıklaması için: Temel 72 sa → VIP 24 sa → Acil 4 sa.
    """

    name: str
    sla_hours: int
    priority_score: int


# --- Bileşen arayüzü ---


class TicketComponent(ABC):
    """Decorator deseni — Component: talebin SLA, öncelik ve bildirim davranışı arayüzü.

    Hem çıplak talep (BasicTicket) hem de her sarmalayıcı bu arayüzü uygular;
    bu yüzden bir decorator başka bir decorator'ı sarabilir (Liskov: her
    decorator bir TicketComponent'tir).
    """

    @property
    @abstractmethod
    def ticket(self) -> Ticket: ...

    @abstractmethod
    def sla_hours(self) -> int:
        """Talebin en geç kaç saat içinde çözülmesi gerektiği."""

    @abstractmethod
    def priority_score(self) -> int:
        """Sıralama için öncelik puanı; büyük olan önce ele alınır."""

    @abstractmethod
    def notify(self) -> list[Notification]:
        """Talep açıldığında gönderilmesi gereken bildirimler."""

    @abstractmethod
    def layers(self) -> list[BehaviorLayer]:
        """Zincirin katmanları, en içten dışa; her biri kendisi uygulandıktan sonraki değerlerle."""


# --- Somut bileşen ---


class BasicTicket(TicketComponent):
    """Decorator deseni — Concrete Component: hiçbir özelliği olmayan talebin varsayılan davranışı."""

    LAYER_NAME = "Temel talep"
    SLA_HOURS = 72
    PRIORITY_SCORE = 10

    def __init__(self, ticket: Ticket) -> None:
        self._ticket = ticket

    @property
    def ticket(self) -> Ticket:
        return self._ticket

    def sla_hours(self) -> int:
        return self.SLA_HOURS

    def priority_score(self) -> int:
        return self.PRIORITY_SCORE

    def notify(self) -> list[Notification]:
        return [
            Notification(
                NotificationChannel.IN_APP,
                NotificationAudience.TECHNICIANS,
                f"Yeni talep: {self._ticket.title}",
            )
        ]

    def layers(self) -> list[BehaviorLayer]:
        return [BehaviorLayer(self.LAYER_NAME, self.sla_hours(), self.priority_score())]


# --- Decorator'lar ---


class TicketDecorator(TicketComponent):
    """Decorator deseni — Decorator: varsayılan olarak her çağrıyı içteki nesneye devreder.

    Alt sınıflar yalnızca değiştirmek istedikleri metodu ezer ve katmanın adını
    (`LAYER_NAME`) verir.
    """

    LAYER_NAME: str

    def __init__(self, inner: TicketComponent) -> None:
        self._inner = inner

    @property
    def ticket(self) -> Ticket:
        return self._inner.ticket

    def sla_hours(self) -> int:
        return self._inner.sla_hours()

    def priority_score(self) -> int:
        return self._inner.priority_score()

    def notify(self) -> list[Notification]:
        return self._inner.notify()

    def layers(self) -> list[BehaviorLayer]:
        # İçteki katmanlar + bu katman (kendi sla_hours/priority_score'u çok biçimli olarak hesaplanır)
        return self._inner.layers() + [BehaviorLayer(self.LAYER_NAME, self.sla_hours(), self.priority_score())]


class VipTicket(TicketDecorator):
    """Decorator deseni — Concrete Decorator: VIP taleplerin SLA süresini en geç 24 saate indirir,
    öncelik puanını artırır ve BT yöneticisine e-posta bildirimi ekler."""

    LAYER_NAME = "VIP"
    MAX_SLA_HOURS = 24
    PRIORITY_BONUS = 20

    def sla_hours(self) -> int:
        # min: içteki SLA zaten daha sıkıysa (örn. Acil) onu bozmaz
        return min(self._inner.sla_hours(), self.MAX_SLA_HOURS)

    def priority_score(self) -> int:
        return self._inner.priority_score() + self.PRIORITY_BONUS

    def notify(self) -> list[Notification]:
        return self._inner.notify() + [
            Notification(
                NotificationChannel.EMAIL,
                NotificationAudience.IT_MANAGERS,
                f"VIP kullanıcının talebi: {self.ticket.title}",
            )
        ]


class UrgentTicket(TicketDecorator):
    """Decorator deseni — Concrete Decorator: acil taleplerin SLA süresini en geç 4 saate indirir,
    öncelik puanını artırır ve nöbetçi teknisyene SMS bildirimi ekler."""

    LAYER_NAME = "Acil"
    MAX_SLA_HOURS = 4
    PRIORITY_BONUS = 50

    def sla_hours(self) -> int:
        return min(self._inner.sla_hours(), self.MAX_SLA_HOURS)

    def priority_score(self) -> int:
        return self._inner.priority_score() + self.PRIORITY_BONUS

    def notify(self) -> list[Notification]:
        return self._inner.notify() + [
            Notification(
                NotificationChannel.SMS,
                NotificationAudience.ON_CALL_TECHNICIANS,
                f"ACİL talep: {self.ticket.title}",
            )
        ]


# --- Factory ---


class TicketComponentFactory:
    """Factory deseni: `ticket.modifiers` listesine göre ticket'ı decorator'larla sarar.

    Sözlükteki sıra giydirme sırasıdır (ilk eleman en içte). Yeni bir modifier
    eklemek için yalnızca yeni bir decorator sınıfı yazıp buraya eklemek yeter;
    Factory'yi kullanan kodlar değişmez (Açık/Kapalı ilkesi).
    """

    DECORATORS: dict[TicketModifier, type[TicketDecorator]] = {
        TicketModifier.VIP: VipTicket,
        TicketModifier.URGENT: UrgentTicket,
    }

    @classmethod
    def create(cls, ticket: Ticket) -> TicketComponent:
        behavior: TicketComponent = BasicTicket(ticket)
        for modifier, decorator in cls.DECORATORS.items():
            if modifier in ticket.modifiers:
                behavior = decorator(behavior)
        return behavior
