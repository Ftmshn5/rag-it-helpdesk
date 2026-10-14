"""Application katmanının olay dinleyicileri (Observer deseni — Concrete Observer).

Read model güncellemeleri (projektörler) ve loglama altyapıdadır; burada iş
akışını tetikleyen dinleyiciler bulunur: AI yanıtı ve bildirimler.
"""

from abc import abstractmethod
from collections.abc import Callable
from typing import TypeVar

from app.application.commands.ai_answers import AutoAnswerTicketCommand, AutoAnswerTicketHandler
from app.application.commands.notifications import (
    NotifyTicketCommand,
    NotifyTicketCreatedCommand,
    NotifyTicketStatusChangedCommand,
    TicketNotificationHandler,
)
from app.application.interfaces.event_bus import EventHandler
from app.application.interfaces.task_runner import TaskRunner
from app.domain.events import TicketCreated, TicketEvent, TicketStatusChanged


class AutoAnswerScheduler(EventHandler[TicketCreated]):
    """Observer deseni — Concrete Observer: yeni talep açılınca AI yanıt işini (UC-14) kuyruğa verir.

    Talep açma kodu AI'dan habersizdir; bağlantıyı bu dinleyici kurar. Gerçek LLM
    yavaş olduğu için iş TaskRunner'a verilir: talep açma isteği AI'ı beklemez.

    Handler her işte yeniden oluşturulur (fabrika ile): her çalışma kendi Unit of
    Work'ünü, dolayısıyla kendi transaction'ını alır.
    """

    def __init__(self, handler_factory: Callable[[], AutoAnswerTicketHandler], task_runner: TaskRunner) -> None:
        self._handler_factory = handler_factory
        self._task_runner = task_runner

    def handle(self, event: TicketCreated) -> None:
        self.schedule(event.ticket_id)

    def schedule(self, ticket_id: int) -> None:
        """İşi kuyruğa verir (olay ve açılıştaki kurtarma bu metodu kullanır)."""
        self._task_runner.submit(
            lambda: self._handler_factory().handle(AutoAnswerTicketCommand(ticket_id=ticket_id)),
            f"AI yanıtı (talep {ticket_id})",
        )


TTicketEvent = TypeVar("TTicketEvent", bound=TicketEvent)


class TicketNotifier(EventHandler[TTicketEvent]):
    """Observer deseni — Concrete Observer (soyut taban): bir talep olayından bildirim üretir.

    Her alt sınıf hangi olayı dinlediğini (`source_event`) ve olayı hangi
    bildirim command'ına çevirdiğini (`command_for`) bildirir. Handler her olayda
    yeniden oluşturulur: her bildirim işi kendi Unit of Work'ünü alır.
    """

    source_event: type[TTicketEvent]

    def __init__(self, handler_factory: Callable[[], TicketNotificationHandler]) -> None:
        self._handler_factory = handler_factory

    def handle(self, event: TTicketEvent) -> None:
        self._handler_factory().handle(self.command_for(event))

    @abstractmethod
    def command_for(self, event: TTicketEvent) -> NotifyTicketCommand: ...


class TicketCreatedNotifier(TicketNotifier[TicketCreated]):
    """Observer deseni — Concrete Observer: yeni talep → Decorator zincirinin bildirimleri."""

    source_event = TicketCreated

    def command_for(self, event: TicketCreated) -> NotifyTicketCreatedCommand:
        return NotifyTicketCreatedCommand(ticket_id=event.ticket_id, actor_id=event.requester_id)


class TicketStatusNotifier(TicketNotifier[TicketStatusChanged]):
    """Observer deseni — Concrete Observer: durum değişti → yeni durumun bildirimleri."""

    source_event = TicketStatusChanged

    def command_for(self, event: TicketStatusChanged) -> NotifyTicketStatusChangedCommand:
        return NotifyTicketStatusChangedCommand(
            ticket_id=event.ticket_id, actor_id=event.actor_id, new_status=event.new_status
        )
