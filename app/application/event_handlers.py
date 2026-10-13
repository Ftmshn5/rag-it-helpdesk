"""Application katmanının olay dinleyicileri (Observer deseni — Concrete Observer).

Read model güncellemeleri (projektörler) ve loglama altyapıdadır; burada iş
akışını tetikleyen dinleyiciler bulunur.
"""

from collections.abc import Callable

from app.application.commands.ai_answers import AutoAnswerTicketCommand, AutoAnswerTicketHandler
from app.application.interfaces.event_bus import EventHandler
from app.application.interfaces.task_runner import TaskRunner
from app.domain.events import TicketCreated


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
