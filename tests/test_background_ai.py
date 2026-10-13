"""AI yanıtının arka planda üretilmesi: iş yürütücüler, olay bağlantısı, açılışta kurtarma."""

import logging
import threading

from app.application.commands.ai_answers import AutoAnswerTicketHandler
from app.application.commands.tickets import CreateTicketCommand, CreateTicketHandler
from app.application.interfaces.task_runner import TaskRunner
from app.core import dependencies
from app.domain.enums import TicketCategory, TicketStatus
from app.domain.user import User
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.db.projections import TicketSummaryProjector
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from app.infrastructure.events.task_runner import BackgroundTaskRunner, InlineTaskRunner
from tests.fakes import FakeEventBus, FakeUnitOfWork, subscribe_all


class RecordingTaskRunner(TaskRunner):
    """İşleri çalıştırmadan biriktirir; test istediğinde çalıştırır."""

    def __init__(self) -> None:
        self.tasks: list[tuple[str, object]] = []

    def submit(self, task, description: str) -> None:
        self.tasks.append((description, task))

    def run_all(self) -> None:
        for _, task in self.tasks:
            task()


# --- Yürütücüler ---


def test_inline_runner_runs_immediately():
    calls = []
    InlineTaskRunner().submit(lambda: calls.append(1), "iş")
    assert calls == [1]


def test_background_runner_runs_tasks_in_order_on_another_thread():
    runner = BackgroundTaskRunner(max_workers=1, thread_name_prefix="test")
    done = threading.Event()
    seen: list[tuple[int, str]] = []

    for index in range(3):
        runner.submit(lambda i=index: seen.append((i, threading.current_thread().name)), f"iş {index}")
    runner.submit(done.set, "son")

    assert done.wait(timeout=5)
    assert [i for i, _ in seen] == [0, 1, 2]  # tek işçi: sıra korunur
    assert all(name.startswith("test") for _, name in seen)
    assert threading.current_thread().name not in {name for _, name in seen}
    runner.shutdown()


def test_background_failure_is_logged_and_does_not_stop_the_queue(caplog):
    runner = BackgroundTaskRunner(max_workers=1)
    done = threading.Event()

    def broken() -> None:
        raise RuntimeError("veritabanı koptu")

    with caplog.at_level(logging.ERROR):
        runner.submit(broken, "AI yanıtı (talep 9)")
        runner.submit(done.set, "sonraki")
        assert done.wait(timeout=5)

    assert "Arka plan işi başarısız: AI yanıtı (talep 9)" in caplog.text
    runner.shutdown()


# --- Olay bağlantısı ---


def test_ticket_creation_returns_before_ai_runs():
    """Talep açma isteği AI'ı beklemez: talep OPEN döner, AI sonra çalışır."""
    bus = InMemoryEventBus()
    uow = FakeUnitOfWork(bus)
    runner = RecordingTaskRunner()
    subscribe_all(bus, lambda: AutoAnswerTicketHandler(uow, FakeAiSupport(), 0.6), task_runner=runner)
    requester = uow.users.add(User(full_name="Ayşe", email="a@x.edu"))

    ticket_id = CreateTicketHandler(uow).handle(
        CreateTicketCommand(actor_id=requester.id, title="Şifremi unuttum", description="", category=TicketCategory.ACCOUNT)
    )

    assert uow.tickets.get(ticket_id).status == TicketStatus.OPEN
    assert [description for description, _ in runner.tasks] == [f"AI yanıtı (talep {ticket_id})"]

    runner.run_all()  # arka plan işi tamamlandı
    assert uow.tickets.get(ticket_id).status == TicketStatus.AI_ANSWERED


# --- Açılışta kurtarma ---


def test_open_tickets_are_requeued_on_startup(session_factory):
    uow = SqlAlchemyUnitOfWork(FakeEventBus(), session_factory)  # FakeEventBus: AI tetiklenmez
    with uow:
        requester = uow.users.add(User(full_name="Bekleyen", email="resume@test.edu"))
        uow.commit()
    open_id = CreateTicketHandler(uow).handle(
        CreateTicketCommand(actor_id=requester.id, title="Yazıcı", description="-", category=TicketCategory.HARDWARE)
    )
    TicketSummaryProjector(session_factory).refresh(open_id)
    runner = RecordingTaskRunner()

    count = dependencies.resume_pending_auto_answers(InMemoryEventBus(), runner, session_factory)

    descriptions = [description for description, _ in runner.tasks]
    assert f"AI yanıtı (talep {open_id})" in descriptions
    assert count == len(descriptions)
