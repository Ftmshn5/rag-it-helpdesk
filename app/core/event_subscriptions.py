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
    DeviceAssigned,
    DeviceDetailsUpdated,
    DeviceRegistered,
    DeviceRetired,
    DeviceReturned,
    DomainEvent,
    MaintenanceCompleted,
    MaintenanceStarted,
    ScreenshotAttached,
    TicketCommentAdded,
    TicketCreated,
    TicketStatusChanged,
    TicketUrgencyChanged,
)
from app.infrastructure.db.projections import DeviceInventoryProjector, TicketSummaryProjector
from app.infrastructure.events.task_runner import InlineTaskRunner, TaskRunner

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


# device_inventory satırını etkileyen olaylar; hepsi device_id taşır
DEVICE_INVENTORY_EVENTS = (
    DeviceRegistered,
    DeviceDetailsUpdated,
    DeviceRetired,
    DeviceAssigned,
    DeviceReturned,
    MaintenanceStarted,
    MaintenanceCompleted,
)


def log_event(event: DomainEvent) -> None:
    logger.info("Olay: %s", event)


def submit_auto_answer(
    runner: TaskRunner,
    make_auto_answer_handler: Callable[[], AutoAnswerTicketHandler],
    ticket_id: int,
) -> None:
    """AI yanıt işini kuyruğa verir (olay dinleyicisi ve açılıştaki kurtarma kullanır)."""
    runner.submit(
        lambda: make_auto_answer_handler().handle(AutoAnswerTicket(ticket_id=ticket_id)),
        f"AI yanıtı (talep {ticket_id})",
    )


def register_subscribers(
    event_bus: EventBus,
    *,
    make_auto_answer_handler: Callable[[], AutoAnswerTicketHandler],
    ticket_summary_projector: TicketSummaryProjector | None = None,
    device_inventory_projector: DeviceInventoryProjector | None = None,
    task_runner: TaskRunner | None = None,
) -> None:
    """Dinleyicileri kaydeder.

    Handler'lar her olayda yeniden oluşturulur (fabrika fonksiyonu ile): her
    çalışma kendi Unit of Work'ünü, dolayısıyla kendi transaction'ını alır.
    Projektörler verilmezse (veritabanısız testler) read model'ler güncellenmez.
    task_runner verilmezse yavaş işler de hemen (aynı thread'de) çalışır.
    """
    runner = task_runner or InlineTaskRunner()

    # DomainEvent taban sınıfına abonelik → tüm olaylar loglanır
    event_bus.subscribe(DomainEvent, log_event)

    # UC-14: yeni talep → AI asistan otomatik yanıt üretir. Gerçek LLM yavaş
    # olduğu için iş yürütücüye verilir: talep açma isteği AI'ı beklemez.
    event_bus.subscribe(
        TicketCreated,
        lambda event: submit_auto_answer(runner, make_auto_answer_handler, event.ticket_id),
    )

    # CQRS: yazma tarafındaki her talep değişikliği okuma modelini günceller
    if ticket_summary_projector is not None:
        for event_type in TICKET_SUMMARY_EVENTS:
            event_bus.subscribe(
                event_type, lambda event: ticket_summary_projector.refresh(event.ticket_id)
            )

    if device_inventory_projector is not None:
        for event_type in DEVICE_INVENTORY_EVENTS:
            event_bus.subscribe(
                event_type, lambda event: device_inventory_projector.refresh(event.device_id)
            )
