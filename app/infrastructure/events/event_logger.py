"""Tüm domain olaylarını loglayan dinleyici."""

import logging

from app.application.interfaces.event_bus import EventHandler
from app.domain.events import DomainEvent

logger = logging.getLogger("app.events")


class EventLogger(EventHandler[DomainEvent]):
    """Observer deseni — Concrete Observer: DomainEvent tabanına abone olur, her olayı loglar."""

    def handle(self, event: DomainEvent) -> None:
        logger.info("Olay: %s", event)
