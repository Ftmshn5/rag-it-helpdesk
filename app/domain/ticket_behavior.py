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
    notify():          [ekip] → + [BT yöneticisi] → + [nöbetçi teknisyen SMS]

FACTORY
-------
Veritabanında decorator nesnesi saklanmaz, yalnızca `ticket.modifiers` listesi
(örn. ["VIP", "URGENT"]) tutulur. TicketComponentFactory bu listeye bakarak
doğru sarmalayıcıları doğru sırada giydirir; ticket'ı kullanan kod hangi
decorator'ların uygulandığını bilmek zorunda kalmaz.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from app.domain.enums import TicketModifier
from app.domain.ticket import Ticket


class NotificationChannel(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"


@dataclass(frozen=True)
class Notification:
    """Gönderilmesi gereken bir bildirimin tarifi.

    Domain bildirimi göndermez, yalnızca "kime, hangi kanaldan, ne" sorusunu
    cevaplar. Gönderme işi altyapıdadır (ileride bir event dinleyicisi).
    """

    channel: NotificationChannel
    recipient: str
    message: str


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


# --- Somut bileşen ---


class BasicTicket(TicketComponent):
    """Decorator deseni — Concrete Component: hiçbir özelliği olmayan talebin varsayılan davranışı."""

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
                "technicians",
                f"Yeni talep: {self._ticket.title}",
            )
        ]


# --- Decorator'lar ---


class TicketDecorator(TicketComponent):
    """Decorator deseni — Decorator: varsayılan olarak her çağrıyı içteki nesneye devreder.

    Alt sınıflar yalnızca değiştirmek istedikleri metodu ezer.
    """

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


class VipTicket(TicketDecorator):
    """Decorator deseni — Concrete Decorator: VIP taleplerin SLA süresini en geç 24 saate indirir,
    öncelik puanını artırır ve BT yöneticisine e-posta bildirimi ekler."""

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
                "it_manager",
                f"VIP kullanıcının talebi: {self.ticket.title}",
            )
        ]


class UrgentTicket(TicketDecorator):
    """Decorator deseni — Concrete Decorator: acil taleplerin SLA süresini en geç 4 saate indirir,
    öncelik puanını artırır ve nöbetçi teknisyene SMS bildirimi ekler."""

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
                "on_call_technician",
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
