"""AI command'ları (UC-14: yeni talebe otomatik yanıt üret).

Aktör kullanıcı değil, AI asistandır: bu command bir HTTP isteğiyle değil,
TicketCreated olayını dinleyen bir Observer tarafından çağrılır (bkz.
app/core/event_subscriptions.py). Talep bu noktada zaten kaydedilmiştir;
AI ne yaparsa yapsın talep kaybolmaz.
"""

import logging
from dataclasses import dataclass

from app.application.commands.common import get_ticket_or_raise
from app.application.interfaces.ai_support import AiSupportFacade, AutoAnswer
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.enums import TicketStatus
from app.domain.events import AiAnswerRecorded, TicketStatusChanged
from app.domain.ticket import AIResponse

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AutoAnswerTicket:
    ticket_id: int


class AutoAnswerTicketHandler:
    def __init__(self, uow: UnitOfWork, ai_support: AiSupportFacade, threshold: float) -> None:
        self.uow = uow
        self.ai_support = ai_support
        self.threshold = threshold

    def handle(self, command: AutoAnswerTicket) -> None:
        with self.uow:
            ticket = get_ticket_or_raise(self.uow, command.ticket_id)
            if ticket.status != TicketStatus.OPEN:
                # Aynı olay iki kez işlenirse ikinci kez yanıt üretme (idempotent)
                return

            answer = self._ask_ai(ticket)

            old_status = ticket.status
            shown_to_user = ticket.receive_ai_answer(  # iş kuralı 4 domain'de
                answer.confidence if answer else None, self.threshold
            )

            # Düşük güvenli yanıt da saklanır: kullanıcıya gösterilmez ama
            # istatistik (UC-12) ve AI kalitesinin izlenmesi için değerlidir.
            response = None
            if answer is not None:
                response = self.uow.ai_responses.add(
                    AIResponse(
                        ticket_id=ticket.id,
                        answer=answer.answer,
                        confidence=answer.confidence,
                        sources=answer.sources,
                    )
                )
            self.uow.tickets.update(ticket)

            self.uow.add_event(
                AiAnswerRecorded(
                    ticket_id=ticket.id,
                    ai_response_id=response.id if response else None,
                    confidence=answer.confidence if answer else None,
                    escalated=not shown_to_user,
                )
            )
            self.uow.add_event(
                TicketStatusChanged(
                    ticket_id=ticket.id,
                    old_status=old_status,
                    new_status=ticket.status,
                    actor_id=None,  # AI asistan
                    assignee_id=ticket.assignee_id,
                )
            )
            self.uow.commit()

    def _ask_ai(self, ticket) -> AutoAnswer | None:
        """AI'a sorar; AI hata verirse None döner (talep eskale edilir, akış durmaz)."""
        try:
            return self.ai_support.try_auto_resolve(ticket)
        except Exception:
            logger.exception("AI yanıtı üretilemedi (talep %s); talep eskale edilecek", ticket.id)
            return None
