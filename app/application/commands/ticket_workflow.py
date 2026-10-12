"""Ticket iş akışı command'ları.

UC-10 (yönetici talebi teknisyene atar), UC-06 (teknisyen durumu günceller,
not ekler), çözümü onaylama (kapatma) ve yeniden açma.

Hangi geçişin hangi durumda mümkün olduğuna State deseni (domain) karar verir.
Bu modül yalnızca "kim yapabilir" sorusunu cevaplar ve akışı yürütür.

Tüm geçişler aynı akışı izlediği için ortak taban sınıf kullanılır
(Template Method): yükle → yetki → geçiş → kaydet → olay → commit.
Alt sınıflar yalnızca `authorize` ve `apply` adımlarını doldurur.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.application.commands.common import ALL_ROLES, get_ticket_or_raise, require_role
from app.application.errors import NotFoundError, PermissionDeniedError
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.enums import UserRole
from app.domain.events import TicketCommentAdded, TicketStatusChanged
from app.domain.ticket import Ticket, TicketComment
from app.domain.user import User

# --- Yetki kontrolleri ---


def require_admin(actor: User, ticket: Ticket) -> None:
    if actor.role != UserRole.ADMIN:
        raise PermissionDeniedError("Bu işlem için yetkiniz yok.")


def require_assigned_technician(actor: User, ticket: Ticket) -> None:
    if actor.id != ticket.assignee_id:
        raise PermissionDeniedError("Bu talep size atanmamış.")


def require_requester(actor: User, ticket: Ticket) -> None:
    if actor.id != ticket.requester_id:
        raise PermissionDeniedError("Bu işlemi yalnızca talep sahibi yapabilir.")


def require_requester_or_admin(actor: User, ticket: Ticket) -> None:
    if actor.id != ticket.requester_id and actor.role != UserRole.ADMIN:
        raise PermissionDeniedError("Bu işlemi yalnızca talep sahibi veya yönetici yapabilir.")


# --- Ortak akış ---


@dataclass(frozen=True, kw_only=True)
class TicketCommand:
    actor_id: int
    ticket_id: int


class TicketTransitionHandler(ABC):
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: TicketCommand) -> None:
        with self.uow:
            actor = require_role(self.uow, command.actor_id, *ALL_ROLES)
            ticket = get_ticket_or_raise(self.uow, command.ticket_id)
            self.authorize(actor, ticket)

            old_status = ticket.status
            self.apply(ticket, command)  # geçersiz geçişte State hata fırlatır → commit yok

            self.uow.tickets.update(ticket)
            self.uow.add_event(
                TicketStatusChanged(
                    ticket_id=ticket.id,
                    old_status=old_status,
                    new_status=ticket.status,
                    actor_id=actor.id,
                    assignee_id=ticket.assignee_id,
                )
            )
            self.uow.commit()

    @abstractmethod
    def authorize(self, actor: User, ticket: Ticket) -> None: ...

    @abstractmethod
    def apply(self, ticket: Ticket, command: TicketCommand) -> None: ...


# --- UC-10: talebi teknisyene ata ---


@dataclass(frozen=True, kw_only=True)
class AssignTicket(TicketCommand):
    technician_id: int


class AssignTicketHandler(TicketTransitionHandler):
    def authorize(self, actor: User, ticket: Ticket) -> None:
        require_admin(actor, ticket)

    def apply(self, ticket: Ticket, command: AssignTicket) -> None:
        technician = self.uow.users.get(command.technician_id)
        if technician is None:
            raise NotFoundError("Atanacak kullanıcı bulunamadı.")
        ticket.assign(technician)  # iş kuralı 3 domain'de


# --- UC-06: teknisyen durumu günceller ---


@dataclass(frozen=True, kw_only=True)
class StartWork(TicketCommand):
    pass


class StartWorkHandler(TicketTransitionHandler):
    def authorize(self, actor: User, ticket: Ticket) -> None:
        require_assigned_technician(actor, ticket)

    def apply(self, ticket: Ticket, command: StartWork) -> None:
        ticket.start_work()


@dataclass(frozen=True, kw_only=True)
class ResolveTicket(TicketCommand):
    pass


class ResolveTicketHandler(TicketTransitionHandler):
    def authorize(self, actor: User, ticket: Ticket) -> None:
        require_assigned_technician(actor, ticket)

    def apply(self, ticket: Ticket, command: ResolveTicket) -> None:
        ticket.resolve()


# --- Çözümün onayı / yeniden açma ---


@dataclass(frozen=True, kw_only=True)
class CloseTicket(TicketCommand):
    pass


class CloseTicketHandler(TicketTransitionHandler):
    def authorize(self, actor: User, ticket: Ticket) -> None:
        require_requester_or_admin(actor, ticket)

    def apply(self, ticket: Ticket, command: CloseTicket) -> None:
        ticket.close()


@dataclass(frozen=True, kw_only=True)
class ReopenTicket(TicketCommand):
    pass


class ReopenTicketHandler(TicketTransitionHandler):
    def authorize(self, actor: User, ticket: Ticket) -> None:
        require_requester(actor, ticket)

    def apply(self, ticket: Ticket, command: ReopenTicket) -> None:
        ticket.reopen()


# --- UC-06: not ekle (durum değiştirmez) ---


@dataclass(frozen=True, kw_only=True)
class AddComment(TicketCommand):
    content: str


class AddCommentHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: AddComment) -> int:
        with self.uow:
            actor = require_role(self.uow, command.actor_id, *ALL_ROLES)
            ticket = get_ticket_or_raise(self.uow, command.ticket_id)
            if not ticket.is_participant(actor):
                raise PermissionDeniedError("Bu talebe not ekleme yetkiniz yok.")
            ticket.ensure_open_for_contributions()

            comment = self.uow.ticket_comments.add(
                TicketComment(ticket_id=ticket.id, author_id=actor.id, content=command.content)
            )
            self.uow.add_event(
                TicketCommentAdded(ticket_id=ticket.id, comment_id=comment.id, author_id=actor.id)
            )
            self.uow.commit()
            return comment.id
