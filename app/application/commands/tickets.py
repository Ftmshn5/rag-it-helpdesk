"""Ticket command'ları (UC-01: arıza kaydı oluştur; acil işaretini değiştir).

Factory burada iş akışına bağlanır: kaydedilen ticket TicketBehaviorFactory ile
decorator'larla sarılır ve SLA / öncelik puanı olaya eklenir.
"""

from dataclasses import dataclass

from app.application.commands.base import ActorCommand, CommandHandler
from app.domain.enums import TicketCategory, UserRole
from app.domain.events import TicketCreated, TicketUrgencyChanged
from app.domain.ticket import Ticket
from app.domain.ticket_behavior import TicketBehaviorFactory


@dataclass(frozen=True, kw_only=True)
class CreateTicketCommand(ActorCommand):
    title: str
    description: str
    category: TicketCategory
    is_urgent: bool = False
    device_id: int | None = None


class CreateTicketHandler(CommandHandler[CreateTicketCommand, int]):
    def handle(self, command: CreateTicketCommand) -> int:
        with self._uow:
            # Her rol talep açabilir (teknisyen ve yönetici de arıza bildirebilir)
            requester = self._require_actor(command.actor_id)
            if command.device_id is not None:
                self._get_device(command.device_id)

            ticket = self._uow.tickets.add(
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
            self._uow.add_event(
                TicketCreated(
                    ticket_id=ticket.id,
                    requester_id=requester.id,
                    sla_hours=behavior.sla_hours(),
                    priority_score=behavior.priority_score(),
                )
            )
            self._uow.commit()
            return ticket.id


@dataclass(frozen=True, kw_only=True)
class SetTicketUrgencyCommand(ActorCommand):
    ticket_id: int
    is_urgent: bool


class SetTicketUrgencyHandler(CommandHandler[SetTicketUrgencyCommand, None]):
    def handle(self, command: SetTicketUrgencyCommand) -> None:
        with self._uow:
            self._require_actor(command.actor_id, UserRole.ADMIN)
            ticket = self._get_ticket(command.ticket_id)

            if ticket.is_urgent == command.is_urgent:
                return  # değişiklik yok: kayıt ve olay üretme

            ticket.set_urgent(command.is_urgent)

            self._uow.tickets.update(ticket)
            behavior = TicketBehaviorFactory.create(ticket)
            self._uow.add_event(
                TicketUrgencyChanged(
                    ticket_id=ticket.id,
                    is_urgent=ticket.is_urgent,
                    sla_hours=behavior.sla_hours(),
                    priority_score=behavior.priority_score(),
                )
            )
            self._uow.commit()
