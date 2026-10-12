"""Ticket command'ları (UC-01: arıza kaydı oluştur; acil işaretini değiştir).

Factory burada iş akışına bağlanır: kaydedilen ticket TicketBehaviorFactory ile
decorator'larla sarılır ve SLA / öncelik puanı olaya eklenir.
"""

from dataclasses import dataclass

from app.application.commands.common import (
    ALL_ROLES,
    get_device_or_raise,
    get_ticket_or_raise,
    require_role,
)
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.enums import TicketCategory, UserRole
from app.domain.events import TicketCreated, TicketUrgencyChanged
from app.domain.ticket import Ticket
from app.domain.ticket_behavior import TicketBehaviorFactory


@dataclass(frozen=True, kw_only=True)
class CreateTicket:
    actor_id: int
    title: str
    description: str
    category: TicketCategory
    is_urgent: bool = False
    device_id: int | None = None


class CreateTicketHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: CreateTicket) -> int:
        with self.uow:
            # Her rol talep açabilir (teknisyen ve yönetici de arıza bildirebilir)
            requester = require_role(self.uow, command.actor_id, *ALL_ROLES)
            if command.device_id is not None:
                get_device_or_raise(self.uow, command.device_id)

            ticket = self.uow.tickets.add(
                Ticket.open(
                    requester=requester,
                    title=command.title,
                    description=command.description,
                    category=command.category,
                    is_urgent=command.is_urgent,
                    device_id=command.device_id,
                )
            )

            behavior = TicketBehaviorFactory.create(ticket)
            self.uow.add_event(
                TicketCreated(
                    ticket_id=ticket.id,
                    requester_id=requester.id,
                    sla_hours=behavior.sla_hours(),
                    priority_score=behavior.priority_score(),
                )
            )
            self.uow.commit()
            return ticket.id


@dataclass(frozen=True, kw_only=True)
class SetTicketUrgency:
    actor_id: int
    ticket_id: int
    is_urgent: bool


class SetTicketUrgencyHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: SetTicketUrgency) -> None:
        with self.uow:
            require_role(self.uow, command.actor_id, UserRole.ADMIN)
            ticket = get_ticket_or_raise(self.uow, command.ticket_id)

            if ticket.is_urgent == command.is_urgent:
                return  # değişiklik yok: kayıt ve olay üretme

            ticket.set_urgent(command.is_urgent)

            self.uow.tickets.update(ticket)
            behavior = TicketBehaviorFactory.create(ticket)
            self.uow.add_event(
                TicketUrgencyChanged(
                    ticket_id=ticket.id,
                    is_urgent=ticket.is_urgent,
                    sla_hours=behavior.sla_hours(),
                    priority_score=behavior.priority_score(),
                )
            )
            self.uow.commit()
