"""Olay dinleyicilerinin event bus'a kaydedildiği tek yer.

Yeni bir dinleyici (read model güncelleme, bildirim vb.) eklemek için yalnızca
bu dosyaya bir `subscribe` satırı eklenir; olayı üreten koda dokunulmaz.
"""

import logging

from app.application.interfaces.event_bus import EventBus
from app.domain.events import DomainEvent

logger = logging.getLogger("app.events")


def log_event(event: DomainEvent) -> None:
    logger.info("Olay: %s", event)


def register_subscribers(event_bus: EventBus) -> None:
    # DomainEvent taban sınıfına abonelik → tüm olaylar loglanır
    event_bus.subscribe(DomainEvent, log_event)
