"""Olay dinleyicilerinin event bus'a kaydedildiği tek yer.

Yeni bir dinleyici (read model, bildirim vb.) eklemek için bir EventHandler
sınıfı yazılır ve burada kaydedilir; olayı üreten koda dokunulmaz (Observer).
"""

from app.application.event_handlers import AutoAnswerScheduler, TicketNotifier
from app.application.interfaces.event_bus import EventBus, EventHandler
from app.domain.events import DomainEvent, TicketCreated
from app.infrastructure.db.projections import ReadModelProjection
from app.infrastructure.events.event_logger import EventLogger


class EventSubscriptions:
    """Uygulamanın tüm olay aboneliklerini tanımlar ve bir event bus'a kaydeder.

    Projektörler veya bildiriciler verilmezse (veritabanısız testler) read model'ler
    güncellenmez, bildirim üretilmez.
    """

    def __init__(
        self,
        *,
        auto_answer: AutoAnswerScheduler,
        projectors: tuple[ReadModelProjection, ...] = (),
        notifiers: tuple[TicketNotifier, ...] = (),
        event_logger: EventHandler[DomainEvent] | None = None,
    ) -> None:
        self._auto_answer = auto_answer
        self._projectors = projectors
        self._notifiers = notifiers
        self._event_logger = event_logger or EventLogger()

    def register(self, event_bus: EventBus) -> None:
        # DomainEvent taban sınıfına abonelik → tüm olaylar loglanır
        event_bus.subscribe(DomainEvent, self._event_logger)

        # UC-14: yeni talep → AI asistan otomatik yanıt üretir (arka planda)
        event_bus.subscribe(TicketCreated, self._auto_answer)

        # CQRS: her projektör (zaman çizelgesi dahil), read model'ini etkileyen olaylara abone olur
        for projector in self._projectors:
            for event_type in projector.source_events:
                event_bus.subscribe(event_type, projector)

        # Bildirimler: talep açıldı (Decorator) / durum değişti (State)
        for notifier in self._notifiers:
            event_bus.subscribe(notifier.source_event, notifier)
