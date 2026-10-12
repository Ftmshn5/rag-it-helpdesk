"""Olay dinleyicilerinin event bus'a kaydedildiği tek yer.

Yeni bir dinleyici (read model güncelleme, bildirim vb.) eklemek için yalnızca
bu dosyaya bir `subscribe` satırı eklenir; olayı üreten koda dokunulmaz.
"""

import logging
from collections.abc import Callable

from app.application.commands.ai_answers import AutoAnswerTicket, AutoAnswerTicketHandler
from app.application.interfaces.event_bus import EventBus
from app.domain.events import (
    AiAnswerRecorded,
    AiFeedbackGiven,
    DomainEvent,
    ScreenshotAttached,
    TicketCommentAdded,
    TicketCreated,
    TicketStatusChanged,
    TicketUrgencyChanged,
)
from app.infrastructure.db.projections import TicketSummaryProjector

logger = logging.getLogger("app.events")

# ticket_summary satırını etkileyen olaylar; hepsi ticket_id taşır
TICKET_SUMMARY_EVENTS = (
    TicketCreated,
    TicketStatusChanged,
    TicketUrgencyChanged,
    AiAnswerRecorded,
    AiFeedbackGiven,
    TicketCommentAdded,
    ScreenshotAttached,
)


def log_event(event: DomainEvent) -> None:
    logger.info("Olay: %s", event)


def register_subscribers(
    event_bus: EventBus,
    *,
    make_auto_answer_handler: Callable[[], AutoAnswerTicketHandler],
    ticket_summary_projector: TicketSummaryProjector | None = None,
) -> None:
    """Dinleyicileri kaydeder.

    Handler'lar her olayda yeniden oluşturulur (fabrika fonksiyonu ile): her
    çalışma kendi Unit of Work'ünü, dolayısıyla kendi transaction'ını alır.
    Projektör verilmezse (veritabanısız testler) read model güncellenmez.
    """
    # DomainEvent taban sınıfına abonelik → tüm olaylar loglanır
    event_bus.subscribe(DomainEvent, log_event)

    # UC-14: yeni talep → AI asistan otomatik yanıt üretir
    event_bus.subscribe(
        TicketCreated,
        lambda event: make_auto_answer_handler().handle(
            AutoAnswerTicket(ticket_id=event.ticket_id)
        ),
    )

    # CQRS: yazma tarafındaki her talep değişikliği okuma modelini günceller
    if ticket_summary_projector is not None:
        for event_type in TICKET_SUMMARY_EVENTS:
            event_bus.subscribe(
                event_type, lambda event: ticket_summary_projector.refresh(event.ticket_id)
            )
