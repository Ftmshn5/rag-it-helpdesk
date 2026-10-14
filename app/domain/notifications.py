"""Bildirimler: kime, hangi kanaldan, ne söyleneceği.

İki kavram ayrıdır:

- `Notification` bir *tariftir* (değer nesnesi): "teknisyenlere uygulama içi
  'Yeni talep' bildirimi gitmeli". Hangi tariflerin gerektiğine domain karar
  verir: talep açılınca Decorator zinciri (`TicketComponent.notify`), durum
  değişince yeni durumun State nesnesi (`TicketState.entry_notifications`).
- `UserNotification` belirli bir kullanıcıya gönderilmiş, saklanan bildirimdir
  (varlık). Kullanıcı okuyunca `mark_read` ile işaretlenir.

Tarifteki alıcı bir kişi değil bir *kitledir* (`NotificationAudience`); kitleyi
kişilere çevirmek (örn. "tüm teknisyenler") veri gerektirdiği için application
katmanının işidir. Domain bildirimi göndermez; teslim altyapıdadır (Strategy).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.clock import Clock
from app.domain.entity import Entity


class NotificationChannel(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"


class NotificationAudience(StrEnum):
    """Bildirimin kime gideceği (kişiye çevrilmesi application katmanında)."""

    TECHNICIANS = "TECHNICIANS"  # tüm teknisyenler
    IT_MANAGERS = "IT_MANAGERS"  # BT yöneticileri (ADMIN)
    ON_CALL_TECHNICIANS = "ON_CALL_TECHNICIANS"  # nöbetçi: kıdemli (L2) teknisyenler
    REQUESTER = "REQUESTER"  # talep sahibi
    ASSIGNEE = "ASSIGNEE"  # atanan teknisyen


@dataclass(frozen=True)
class Notification:
    """Gönderilmesi gereken bir bildirimin tarifi (değer nesnesi)."""

    channel: NotificationChannel
    audience: NotificationAudience
    message: str


class UserNotification(Entity):
    """Bir kullanıcıya gönderilmiş bildirim. Yalnızca okundu olarak işaretlenebilir."""

    def __init__(
        self,
        *,
        id: int | None = None,
        recipient_id: int,
        ticket_id: int | None,
        channel: NotificationChannel,
        message: str,
        created_at: datetime | None = None,
        read_at: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self._recipient_id = recipient_id
        self._ticket_id = ticket_id
        self._channel = channel
        self._message = message
        self._created_at = created_at or Clock.now()
        self._read_at = read_at

    @classmethod
    def deliver(cls, notification: Notification, *, recipient_id: int, ticket_id: int | None) -> "UserNotification":
        """Factory Method: bir tariften, belirli bir kullanıcıya ait bildirimi üretir."""
        return cls(
            recipient_id=recipient_id,
            ticket_id=ticket_id,
            channel=notification.channel,
            message=notification.message,
        )

    @property
    def recipient_id(self) -> int:
        return self._recipient_id

    @property
    def ticket_id(self) -> int | None:
        return self._ticket_id

    @property
    def channel(self) -> NotificationChannel:
        return self._channel

    @property
    def message(self) -> str:
        return self._message

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def read_at(self) -> datetime | None:
        return self._read_at

    @property
    def is_read(self) -> bool:
        return self._read_at is not None

    def belongs_to(self, user_id: int) -> bool:
        return self._recipient_id == user_id

    def mark_read(self) -> None:
        """Okundu olarak işaretler; zaten okunmuşsa ilk okunma zamanı korunur (idempotent)."""
        if self._read_at is None:
            self._read_at = Clock.now()
