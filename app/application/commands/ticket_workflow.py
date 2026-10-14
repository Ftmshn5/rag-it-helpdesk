"""Ticket iş akışı command'ları.

UC-10 (yönetici talebi teknisyene atar), UC-06 (teknisyen durumu günceller,
not ekler), UC-07 (teknisyen üst seviyeye eskale eder), çözümü onaylama
(kapatma) ve yeniden açma.

Hangi geçişin hangi durumda mümkün olduğuna State deseni (domain) karar verir.
Bu modül yalnızca "kim yapabilir" sorusunu cevaplar ve akışı yürütür.
"""

from abc import abstractmethod
from dataclasses import dataclass

from app.application.commands.base import ActorCommand, CommandHandler
from app.application.errors import PermissionDeniedError
from app.domain.enums import UserRole
from app.domain.events import TicketCommentAdded, TicketStatusChanged
from app.domain.ticket import Ticket, TicketComment
from app.domain.user import User


@dataclass(frozen=True, kw_only=True)
class TicketCommand(ActorCommand):
    """Belirli bir talep üzerinde yapılan command'ların ortak verisi."""

    ticket_id: int


class TicketCommandHandler(CommandHandler[TicketCommand, None]):
    """Talep command'larının ortak tabanı: "kim yapabilir" kontrollerini sağlar."""

    def _ensure_admin(self, actor: User) -> None:
        if actor.role != UserRole.ADMIN:
            raise PermissionDeniedError("Bu işlem için yetkiniz yok.")

    def _ensure_assigned_technician(self, actor: User, ticket: Ticket) -> None:
        if actor.id != ticket.assignee_id:
            raise PermissionDeniedError("Bu talep size atanmamış.")

    def _ensure_requester(self, actor: User, ticket: Ticket) -> None:
        if actor.id != ticket.requester_id:
            raise PermissionDeniedError("Bu işlemi yalnızca talep sahibi yapabilir.")

    def _ensure_requester_or_admin(self, actor: User, ticket: Ticket) -> None:
        if actor.id != ticket.requester_id and actor.role != UserRole.ADMIN:
            raise PermissionDeniedError("Bu işlemi yalnızca talep sahibi veya yönetici yapabilir.")


class TicketTransitionHandler(TicketCommandHandler):
    """Template Method deseni — Abstract Class: tüm durum geçişlerinin ortak akışı.

    Akış sabittir: yükle → yetki → geçiş → kaydet → olay → commit.
    Alt sınıflar (Concrete Class) yalnızca değişen iki adımı doldurur:
    `authorize` (kim yapabilir) ve `apply` (hangi domain metodu çağrılır).
    """

    def handle(self, command: TicketCommand) -> None:
        with self._uow:
            actor = self._require_actor(command.actor_id)
            ticket = self._get_ticket(command.ticket_id)
            self.authorize(actor, ticket)

            old_status = ticket.status
            self.apply(ticket, command)  # geçersiz geçişte State hata fırlatır → commit yok

            self._uow.tickets.update(ticket)
            self._uow.add_event(
                TicketStatusChanged(
                    ticket_id=ticket.id,
                    old_status=old_status,
                    new_status=ticket.status,
                    actor_id=actor.id,
                    assignee_id=ticket.assignee_id,
                )
            )
            self._uow.commit()

    @abstractmethod
    def authorize(self, actor: User, ticket: Ticket) -> None: ...

    @abstractmethod
    def apply(self, ticket: Ticket, command: TicketCommand) -> None: ...


# --- UC-10: talebi teknisyene ata ---


@dataclass(frozen=True, kw_only=True)
class AssignTicketCommand(TicketCommand):
    technician_id: int


class AssignTicketHandler(TicketTransitionHandler):
    def authorize(self, actor: User, ticket: Ticket) -> None:
        self._ensure_admin(actor)

    def apply(self, ticket: Ticket, command: AssignTicketCommand) -> None:
        technician = self._get_user(command.technician_id, "Atanacak kullanıcı bulunamadı.")
        ticket.assign_to(technician)  # iş kuralı 3 domain'de


# --- UC-06: teknisyen durumu günceller ---


@dataclass(frozen=True, kw_only=True)
class StartWorkCommand(TicketCommand):
    pass


class StartWorkHandler(TicketTransitionHandler):
    def authorize(self, actor: User, ticket: Ticket) -> None:
        self._ensure_assigned_technician(actor, ticket)

    def apply(self, ticket: Ticket, command: StartWorkCommand) -> None:
        ticket.start_work()


@dataclass(frozen=True, kw_only=True)
class ResolveTicketCommand(TicketCommand):
    pass


class ResolveTicketHandler(TicketTransitionHandler):
    def authorize(self, actor: User, ticket: Ticket) -> None:
        self._ensure_assigned_technician(actor, ticket)

    def apply(self, ticket: Ticket, command: ResolveTicketCommand) -> None:
        ticket.resolve()


# --- UC-07: üst seviyeye eskalasyon ---


@dataclass(frozen=True, kw_only=True)
class EscalateTicketCommand(TicketCommand):
    reason: str


class EscalateTicketHandler(TicketTransitionHandler):
    """Hangi seviyeye çıkılacağına domain'deki zincir (Chain of Responsibility),
    bu durumda yapılıp yapılamayacağına State karar verir; handler yalnızca
    yetkiyi denetler ve gerekçeyi kaydeder."""

    def authorize(self, actor: User, ticket: Ticket) -> None:
        self._ensure_assigned_technician(actor, ticket)

    def apply(self, ticket: Ticket, command: EscalateTicketCommand) -> None:
        escalated_by = ticket.assignee_id
        ticket.escalate()  # en üst seviyedeyse veya durum uygun değilse hata → commit yok

        # Gerekçe, talebi üstlenecek kıdemli teknisyen için not olarak kalır.
        # Eskale eden artık talebin tarafı değildir; not bu yüzden doğrudan eklenir.
        comment = self._uow.ticket_comments.add(
            TicketComment(
                ticket_id=ticket.id,
                author_id=escalated_by,
                content=f"Üst seviyeye eskale edildi. Gerekçe: {command.reason}",
            )
        )
        self._uow.add_event(TicketCommentAdded(ticket_id=ticket.id, comment_id=comment.id, author_id=escalated_by))


# --- Çözümün onayı / yeniden açma ---


@dataclass(frozen=True, kw_only=True)
class CloseTicketCommand(TicketCommand):
    pass


class CloseTicketHandler(TicketTransitionHandler):
    def authorize(self, actor: User, ticket: Ticket) -> None:
        self._ensure_requester_or_admin(actor, ticket)

    def apply(self, ticket: Ticket, command: CloseTicketCommand) -> None:
        ticket.close()


@dataclass(frozen=True, kw_only=True)
class ReopenTicketCommand(TicketCommand):
    pass


class ReopenTicketHandler(TicketTransitionHandler):
    def authorize(self, actor: User, ticket: Ticket) -> None:
        self._ensure_requester(actor, ticket)

    def apply(self, ticket: Ticket, command: ReopenTicketCommand) -> None:
        ticket.reopen()


# --- UC-06: not ekle (durum değiştirmez) ---


@dataclass(frozen=True, kw_only=True)
class AddCommentCommand(TicketCommand):
    content: str


class AddCommentHandler(CommandHandler[AddCommentCommand, int]):
    def handle(self, command: AddCommentCommand) -> int:
        with self._uow:
            actor = self._require_actor(command.actor_id)
            ticket = self._get_ticket(command.ticket_id)
            if not ticket.is_participant(actor):
                raise PermissionDeniedError("Bu talebe not ekleme yetkiniz yok.")
            ticket.ensure_open_for_contributions()

            comment = self._uow.ticket_comments.add(
                TicketComment(ticket_id=ticket.id, author_id=actor.id, content=command.content)
            )
            self._uow.add_event(TicketCommentAdded(ticket_id=ticket.id, comment_id=comment.id, author_id=actor.id))
            self._uow.commit()
            return comment.id
