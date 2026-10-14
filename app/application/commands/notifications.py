"""Bildirim command'ları.

Talep olaylarından bildirim üretme (aktörü sistem): olayı dinleyen Observer'lar
(bkz. event_handlers.py) bu handler'ları çağırır; talep açan, atayan veya çözen
kod bildirimlerden habersizdir.

Hangi bildirimin gerektiğine domain karar verir:
- talep açılınca Decorator zinciri (`TicketComponent.notify`: VIP → e-posta, Acil → SMS),
- durum değişince yeni durumun State nesnesi (`TicketState.entry_notifications`).

Akış: tarifler → kitle kişilere çevrilir → bildirimler kaydedilir (commit) →
her biri kanalının göndericisiyle (Strategy) teslim edilir.

Kullanıcının bildirimlerini okundu işaretlemesi de buradadır.
"""

from abc import abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from app.application.commands.base import ActorCommand, Command, CommandHandler
from app.application.errors import NotFoundError
from app.application.interfaces.notification_sender import NotificationSender
from app.application.interfaces.repositories import UserRepository
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.enums import SupportLevel, TicketStatus, UserRole
from app.domain.notifications import Notification, NotificationAudience, UserNotification
from app.domain.ticket import Ticket
from app.domain.ticket_behavior import TicketComponentFactory
from app.domain.ticket_state import STATES
from app.domain.user import User

# --- Talep olaylarından bildirim üretme ---


@dataclass(frozen=True, kw_only=True)
class NotifyTicketCommand(Command):
    """Sistem command'ı: bir talep olayının bildirimlerini üret.

    İşlemi yapan kişi (actor_id) kendi işlemi için bildirim almaz.
    """

    ticket_id: int
    actor_id: int | None = None


@dataclass(frozen=True, kw_only=True)
class NotifyTicketCreatedCommand(NotifyTicketCommand):
    pass


@dataclass(frozen=True, kw_only=True)
class NotifyTicketStatusChangedCommand(NotifyTicketCommand):
    new_status: TicketStatus


class NotificationRecipients:
    """Bir bildirim kitlesini (NotificationAudience) kişilere çevirir.

    Her kitlenin kendi çözümleyici metodu vardır; eşleme tek bir sözlükte
    tutulur (if/elif yok). Yeni kitle = yeni metot + sözlükte bir satır.
    """

    def __init__(self, users: UserRepository) -> None:
        self._users = users
        self._resolvers: dict[NotificationAudience, Callable[[Ticket], list[User]]] = {
            NotificationAudience.TECHNICIANS: self._technicians,
            NotificationAudience.IT_MANAGERS: self._it_managers,
            NotificationAudience.ON_CALL_TECHNICIANS: self._on_call_technicians,
            NotificationAudience.REQUESTER: self._requester,
            NotificationAudience.ASSIGNEE: self._assignee,
        }

    def resolve(self, audience: NotificationAudience, ticket: Ticket) -> list[User]:
        return self._resolvers[audience](ticket)

    def _technicians(self, ticket: Ticket) -> list[User]:
        return self._users.list_by_role(UserRole.TECHNICIAN)

    def _it_managers(self, ticket: Ticket) -> list[User]:
        return self._users.list_by_role(UserRole.ADMIN)

    def _on_call_technicians(self, ticket: Ticket) -> list[User]:
        # Nöbet çizelgesi kapsam dışı: acil durumda kıdemli (L2) teknisyenler aranır
        return [user for user in self._technicians(ticket) if user.support_level == SupportLevel.TIER_2]

    def _requester(self, ticket: Ticket) -> list[User]:
        return self._existing(ticket.requester_id)

    def _assignee(self, ticket: Ticket) -> list[User]:
        return self._existing(ticket.assignee_id)

    def _existing(self, user_id: int | None) -> list[User]:
        user = self._users.get(user_id) if user_id is not None else None
        return [user] if user else []


TNotify = TypeVar("TNotify", bound=NotifyTicketCommand)


class TicketNotificationHandler(CommandHandler[TNotify, int]):
    """Template Method deseni — Abstract Class: talep bildirimlerinin ortak akışı.

    Akış sabittir: talebi yükle → tarifleri al → kişilere çevir → kaydet →
    commit → kanalın göndericisiyle (Strategy) teslim et. Alt sınıflar yalnızca
    tariflerin nereden geldiğini (`notifications_for`) tanımlar.

    Teslim commit'ten sonradır: kaydedilemeyen bildirim için e-posta/SMS gitmez.
    Gönderilen bildirim sayısını döner.
    """

    def __init__(self, uow: UnitOfWork, senders: Sequence[NotificationSender]) -> None:
        super().__init__(uow)
        self._senders = {sender.channel: sender for sender in senders}

    def handle(self, command: TNotify) -> int:
        deliveries: list[tuple[User, UserNotification]] = []
        with self._uow:
            ticket = self._uow.tickets.get(command.ticket_id)
            if ticket is None:
                return 0
            recipients = NotificationRecipients(self._uow.users)
            for notification in self.notifications_for(ticket, command):
                for user in recipients.resolve(notification.audience, ticket):
                    if user.id == command.actor_id:
                        continue
                    saved = self._uow.notifications.add(
                        UserNotification.deliver(notification, recipient_id=user.id, ticket_id=ticket.id)
                    )
                    deliveries.append((user, saved))
            self._uow.commit()

        for user, saved in deliveries:
            self._senders[saved.channel].deliver(user, saved)
        return len(deliveries)

    @abstractmethod
    def notifications_for(self, ticket: Ticket, command: TNotify) -> list[Notification]: ...


class NotifyTicketCreatedHandler(TicketNotificationHandler[NotifyTicketCreatedCommand]):
    """Template Method deseni — Concrete Class: yeni talebin bildirimleri Decorator zincirinden gelir."""

    def notifications_for(self, ticket: Ticket, command: NotifyTicketCreatedCommand) -> list[Notification]:
        return TicketComponentFactory.create(ticket).notify()


class NotifyTicketStatusChangedHandler(TicketNotificationHandler[NotifyTicketStatusChangedCommand]):
    """Template Method deseni — Concrete Class: durum değişikliğinin bildirimleri yeni durumun State nesnesinden gelir.

    Olaydaki durum kullanılır (talebin şimdiki durumu değil): bildirim, olayın
    anlattığı geçişe aittir.
    """

    def notifications_for(self, ticket: Ticket, command: NotifyTicketStatusChangedCommand) -> list[Notification]:
        return STATES[command.new_status].entry_notifications(ticket.title)


# --- Kullanıcı bildirimlerini okundu işaretler ---


@dataclass(frozen=True, kw_only=True)
class MarkNotificationsReadCommand(ActorCommand):
    notification_ids: tuple[int, ...] = ()  # boş: tüm okunmamışlar


class MarkNotificationsReadHandler(CommandHandler[MarkNotificationsReadCommand, None]):
    def handle(self, command: MarkNotificationsReadCommand) -> None:
        with self._uow:
            actor = self._require_actor(command.actor_id)
            for notification in self._notifications_to_mark(actor, command):
                notification.mark_read()
                self._uow.notifications.update(notification)
            self._uow.commit()

    def _notifications_to_mark(self, actor: User, command: MarkNotificationsReadCommand) -> list[UserNotification]:
        if not command.notification_ids:
            return self._uow.notifications.list_unread_for(actor.id)
        return [self._get_own_notification(actor, notification_id) for notification_id in command.notification_ids]

    def _get_own_notification(self, actor: User, notification_id: int) -> UserNotification:
        notification = self._uow.notifications.get(notification_id)
        # Başkasının bildirimi "yok" sayılır: varlığı bile sızdırılmaz
        if notification is None or not notification.belongs_to(actor.id):
            raise NotFoundError("Bildirim bulunamadı.")
        return notification
