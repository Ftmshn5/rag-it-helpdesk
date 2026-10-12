"""Olay dinleyicilerinin event bus'a kaydedildiği tek yer.

Yeni bir dinleyici (read model güncelleme, bildirim vb.) eklemek için yalnızca
bu dosyaya bir `subscribe` satırı eklenir; olayı üreten koda dokunulmaz.
"""

import logging
from collections.abc import Callable

from app.application.commands.ai_answers import AutoAnswerTicket, AutoAnswerTicketHandler
from app.application.interfaces.event_bus import EventBus
from app.domain.events import DomainEvent, TicketCreated

logger = logging.getLogger("app.events")


def log_event(event: DomainEvent) -> None:
    logger.info("Olay: %s", event)


def register_subscribers(
    event_bus: EventBus,
    *,
    make_auto_answer_handler: Callable[[], AutoAnswerTicketHandler],
) -> None:
    """Dinleyicileri kaydeder.

    Handler'lar her olayda yeniden oluşturulur (fabrika fonksiyonu ile): her
    çalışma kendi Unit of Work'ünü, dolayısıyla kendi transaction'ını alır.
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
