"""Uygulama içi, senkron event bus.

Olaylar aynı istek içinde, sırayla dinleyicilere iletilir. Mesaj kuyruğu
(RabbitMQ vb.) kullanılmaz; ders projesi ölçeğinde gereksiz karmaşıklık olur.
"""

import logging
from collections import defaultdict

from app.application.interfaces.event_bus import EventBus, EventHandler, TEvent
from app.domain.events import DomainEvent

logger = logging.getLogger(__name__)


class InMemoryEventBus(EventBus):
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[TEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        # __mro__: olayın kendi sınıfı ve üst sınıfları. Böylece DomainEvent'e
        # abone olan bir dinleyici (örn. loglama) tüm olayları alır.
        # Ters sıra: genel dinleyiciler (loglama) özel olanlardan ÖNCE çalışır;
        # özel bir dinleyici iç içe yeni olaylar üretse bile log sırası korunur.
        for event_type in reversed(type(event).__mro__):
            for handler in self._handlers.get(event_type, []):
                try:
                    handler(event)
                except Exception:
                    # Olay commit'ten sonra yayınlanır: yazma işlemi zaten kalıcı.
                    # Bir dinleyicinin hatası diğer dinleyicileri ve isteği
                    # bozmamalı; hata kaydedilir ve devam edilir.
                    logger.exception(
                        "%s olayı işlenirken %s hata verdi",
                        type(event).__name__,
                        getattr(handler, "__qualname__", handler),
                    )
