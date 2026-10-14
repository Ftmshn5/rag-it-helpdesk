"""Bağımlılık enjeksiyonu (Dependency Injection) — uygulamanın "composition root"u.

Hangi arayüzün hangi somut sınıfla karşılanacağına yalnızca burada karar verilir
(UnitOfWork → SqlAlchemyUnitOfWork, EventBus → InMemoryEventBus …). API katmanı
ihtiyaç duyduğu şeyleri FastAPI `Depends` ile buradan alır; somut sınıfları
kendisi oluşturmaz. Testlerde bu fonksiyonlar `app.dependency_overrides` ile
sahteleriyle değiştirilebilir.

Buradaki sağlayıcılar FastAPI'nin `Depends` kalıbı gereği fonksiyondur ve iş
mantığı içermez; yalnızca nesneleri kurup birbirine bağlar. Uygulama ömrü boyunca
tek olması gereken nesneler (veritabanı, AI) `lru_cache` ile bir kez kurulur.
"""

from collections.abc import Callable, Iterator
from functools import lru_cache

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.application.commands.ai_answers import AutoAnswerTicketHandler, EvaluateAiAnswerHandler
from app.application.commands.assignments import AssignDeviceHandler, ReturnDeviceHandler
from app.application.commands.attachments import AttachScreenshotHandler
from app.application.commands.devices import RegisterDeviceHandler, RetireDeviceHandler, UpdateDeviceDetailsHandler
from app.application.commands.maintenance import CompleteMaintenanceHandler, StartMaintenanceHandler
from app.application.commands.notifications import (
    MarkNotificationsReadHandler,
    NotifyTicketCreatedHandler,
    NotifyTicketStatusChangedHandler,
)
from app.application.commands.ticket_workflow import (
    AddCommentHandler,
    AssignTicketHandler,
    CloseTicketHandler,
    EscalateTicketHandler,
    MoveTicketHandler,
    ReopenTicketHandler,
    ResolveTicketHandler,
    StartWorkHandler,
)
from app.application.commands.tickets import CreateTicketHandler, SetTicketUrgencyHandler
from app.application.errors import AuthenticationError
from app.application.event_handlers import AutoAnswerScheduler, TicketCreatedNotifier, TicketStatusNotifier
from app.application.interfaces.ai_support import AiSupportFacade
from app.application.interfaces.event_bus import EventBus
from app.application.interfaces.file_storage import FileStorage
from app.application.interfaces.notification_sender import NotificationSender
from app.application.interfaces.task_runner import TaskRunner
from app.application.interfaces.unit_of_work import UnitOfWork
from app.application.queries.inventory import (
    GetDeviceHandler,
    GetInventoryReportHandler,
    GetMaintenanceHistoryHandler,
    InventoryQueries,
    ListDevicesHandler,
    ListMyDevicesHandler,
)
from app.application.queries.notifications import GetMyNotificationsHandler, NotificationQueries
from app.application.queries.statistics import GetFailureStatisticsHandler, StatisticsQueries
from app.application.queries.tickets import (
    GetAttachmentFileHandler,
    GetTicketDetailHandler,
    ListAllTicketsHandler,
    ListAssignedTicketsHandler,
    ListMyTicketsHandler,
    TicketQueries,
)
from app.application.queries.users import ListUsersHandler, UserQueries
from app.core.config import get_settings
from app.core.event_subscriptions import EventSubscriptions
from app.domain.attachments import ScreenshotValidator
from app.domain.enums import TicketStatus
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.ai.ollama import OllamaEmbeddingProvider, OllamaLlmProvider
from app.infrastructure.ai.rag_ai_support import RagAiSupport, SimilarityConfidence
from app.infrastructure.ai.retriever import PgVectorRetriever
from app.infrastructure.db.models import EMBEDDING_DIMENSION
from app.infrastructure.db.projections import (
    DeviceInventoryProjector,
    TicketSummaryProjector,
    TicketTimelineProjector,
)
from app.infrastructure.db.queries import SqlInventoryQueries, SqlNotificationQueries, SqlTicketQueries, SqlUserQueries
from app.infrastructure.db.session import Database
from app.infrastructure.db.statistics import SqlStatisticsQueries
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from app.infrastructure.notifications.senders import InAppSender, SimulatedEmailSender, SimulatedSmsSender
from app.infrastructure.storage.local_file_storage import LocalFileStorage

# --- Uygulama ömrü boyunca tek nesneler ---


@lru_cache
def get_database() -> Database:
    """Bağlantı havuzu uygulama başına bir kez kurulur ve paylaşılır."""
    return Database(get_settings().database_url)


@lru_cache
def get_ai_support() -> AiSupportFacade:
    """AI implementasyonunu seçen tek yer (AI_PROVIDER ayarı).

    Facade'ın faydası burada görünür: sahte AI'dan gerçek RAG'e geçmek için
    application ve domain katmanında hiçbir şey değişmez, yalnızca bu fonksiyon.
    Strategy'ler (Ollama embedding / LLM) de burada seçilir. Nesneler durum
    tutmadığı için bir kez kurulup paylaşılır (HTTP bağlantı havuzu yeniden kullanılır).
    """
    settings = get_settings()
    if settings.ai_provider == "fake":
        return FakeAiSupport()

    return RagAiSupport(
        embedder=OllamaEmbeddingProvider(
            settings.ollama_base_url,
            settings.embedding_model,
            dimension=EMBEDDING_DIMENSION,
            timeout_seconds=settings.ollama_timeout_seconds,
        ),
        retriever=PgVectorRetriever(get_database().session_factory),
        llm=OllamaLlmProvider(
            settings.ollama_base_url,
            settings.llm_model,
            timeout_seconds=settings.ollama_timeout_seconds,
            max_tokens=settings.llm_max_tokens,
        ),
        confidence=SimilarityConfidence(floor=settings.rag_similarity_floor, ceiling=settings.rag_similarity_ceiling),
        top_k=settings.rag_top_k,
    )


# --- Olaylar ve AI tetikleme ---


def make_auto_answer_handler(event_bus: EventBus) -> AutoAnswerTicketHandler:
    return AutoAnswerTicketHandler(
        SqlAlchemyUnitOfWork(event_bus, get_database().session_factory),
        get_ai_support(),
        get_settings().ai_confidence_threshold,
    )


def create_auto_answer_scheduler(event_bus: EventBus, task_runner: TaskRunner) -> AutoAnswerScheduler:
    return AutoAnswerScheduler(lambda: make_auto_answer_handler(event_bus), task_runner)


def get_notification_senders() -> tuple[NotificationSender, ...]:
    """Bildirim kanallarının teslim stratejilerini seçen tek yer (Strategy).

    Gerçek e-posta/SMS'e geçmek için yalnızca buradaki benzetim sınıfları değişir.
    """
    return (InAppSender(), SimulatedEmailSender(), SimulatedSmsSender())


def create_notifiers(event_bus: EventBus) -> tuple[TicketCreatedNotifier, TicketStatusNotifier]:
    def uow() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(event_bus, get_database().session_factory)

    senders = get_notification_senders()
    return (
        TicketCreatedNotifier(lambda: NotifyTicketCreatedHandler(uow(), senders)),
        TicketStatusNotifier(lambda: NotifyTicketStatusChangedHandler(uow(), senders)),
    )


def create_event_bus(task_runner: TaskRunner) -> EventBus:
    """Uygulama açılışında bir kez çağrılır; dinleyiciler burada kaydedilir."""
    event_bus = InMemoryEventBus()
    session_factory = get_database().session_factory
    EventSubscriptions(
        auto_answer=create_auto_answer_scheduler(event_bus, task_runner),
        projectors=(
            TicketSummaryProjector(session_factory),
            DeviceInventoryProjector(session_factory),
            TicketTimelineProjector(session_factory),
        ),
        notifiers=create_notifiers(event_bus),
    ).register(event_bus)
    return event_bus


def resume_pending_auto_answers(
    event_bus: EventBus, task_runner: TaskRunner, session_factory: Callable[[], Session] | None = None
) -> int:
    """Açılışta, AI yanıtı bekleyen (OPEN) talepleri yeniden kuyruğa alır.

    Arka plan kuyruğu bellekte tutulur; uygulama yeniden başlarsa (örn.
    --reload ile) bekleyen işler kaybolur ve talep OPEN'da kalırdı. Handler
    idempotent olduğu için bir talebin iki kez kuyruğa girmesi zararsızdır.
    """
    with (session_factory or get_database().session_factory)() as session:
        pending = SqlTicketQueries(session).list_all(TicketStatus.OPEN)
    scheduler = create_auto_answer_scheduler(event_bus, task_runner)
    for ticket in pending:
        scheduler.schedule(ticket.ticket_id)
    return len(pending)


# --- İstek başına nesneler ---


def get_event_bus(request: Request) -> EventBus:
    # Tüm istekler aynı bus'ı paylaşır: abonelikler uygulama ömrü boyunca geçerli
    return request.app.state.event_bus


def get_unit_of_work(event_bus: EventBus = Depends(get_event_bus)) -> UnitOfWork:
    # Her istek kendi Unit of Work'ünü (dolayısıyla kendi transaction'ını) alır
    return SqlAlchemyUnitOfWork(event_bus, get_database().session_factory)


def get_file_storage() -> FileStorage:
    return LocalFileStorage(get_settings().upload_dir)


def get_screenshot_validator() -> ScreenshotValidator:
    return ScreenshotValidator(get_settings().max_upload_size_bytes)


def get_current_user_id(x_user_id: int | None = Header(default=None)) -> int:
    """İşlemi yapan kullanıcıyı X-User-Id başlığından alır.

    Gerçek kimlik doğrulama (şifre/token) kapsam dışı; kullanıcının var olup
    olmadığı ve rolü handler'larda kontrol edilir.
    """
    if x_user_id is None:
        raise AuthenticationError("X-User-Id başlığı gerekli.")
    return x_user_id


# --- Command handler'lar ---


def get_register_device_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> RegisterDeviceHandler:
    return RegisterDeviceHandler(uow)


def get_update_device_details_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> UpdateDeviceDetailsHandler:
    return UpdateDeviceDetailsHandler(uow)


def get_retire_device_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> RetireDeviceHandler:
    return RetireDeviceHandler(uow)


def get_assign_device_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> AssignDeviceHandler:
    return AssignDeviceHandler(uow)


def get_return_device_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> ReturnDeviceHandler:
    return ReturnDeviceHandler(uow)


def get_start_maintenance_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> StartMaintenanceHandler:
    return StartMaintenanceHandler(uow)


def get_complete_maintenance_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> CompleteMaintenanceHandler:
    return CompleteMaintenanceHandler(uow)


def get_create_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> CreateTicketHandler:
    return CreateTicketHandler(uow)


def get_set_ticket_urgency_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> SetTicketUrgencyHandler:
    return SetTicketUrgencyHandler(uow)


def get_attach_screenshot_handler(
    uow: UnitOfWork = Depends(get_unit_of_work),
    storage: FileStorage = Depends(get_file_storage),
    validator: ScreenshotValidator = Depends(get_screenshot_validator),
) -> AttachScreenshotHandler:
    return AttachScreenshotHandler(uow, storage, validator)


def get_assign_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> AssignTicketHandler:
    return AssignTicketHandler(uow)


def get_start_work_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> StartWorkHandler:
    return StartWorkHandler(uow)


def get_resolve_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> ResolveTicketHandler:
    return ResolveTicketHandler(uow)


def get_close_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> CloseTicketHandler:
    return CloseTicketHandler(uow)


def get_reopen_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> ReopenTicketHandler:
    return ReopenTicketHandler(uow)


def get_escalate_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> EscalateTicketHandler:
    return EscalateTicketHandler(uow)


def get_move_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> MoveTicketHandler:
    return MoveTicketHandler(uow)


def get_add_comment_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> AddCommentHandler:
    return AddCommentHandler(uow)


def get_evaluate_ai_answer_handler(uow: UnitOfWork = Depends(get_unit_of_work)) -> EvaluateAiAnswerHandler:
    return EvaluateAiAnswerHandler(uow)


# --- Okuma tarafı (queries): Unit of Work yok, düz salt-okunur oturum ---


def get_db_session() -> Iterator[Session]:
    """Okuma tarafı (queries) için düz oturum; yazma işlemleri UnitOfWork kullanır."""
    yield from get_database().sessions()


def get_database_status() -> bool:
    return get_database().is_available()


def get_ticket_queries(session: Session = Depends(get_db_session)) -> TicketQueries:
    return SqlTicketQueries(session)


def get_user_queries(session: Session = Depends(get_db_session)) -> UserQueries:
    return SqlUserQueries(session)


def get_inventory_queries(session: Session = Depends(get_db_session)) -> InventoryQueries:
    return SqlInventoryQueries(session)


def get_notification_queries(session: Session = Depends(get_db_session)) -> NotificationQueries:
    return SqlNotificationQueries(session)


def get_statistics_queries(session: Session = Depends(get_db_session)) -> StatisticsQueries:
    return SqlStatisticsQueries(session)


def get_list_users_handler(users: UserQueries = Depends(get_user_queries)) -> ListUsersHandler:
    return ListUsersHandler(users)


def get_list_my_tickets_handler(
    tickets: TicketQueries = Depends(get_ticket_queries), users: UserQueries = Depends(get_user_queries)
) -> ListMyTicketsHandler:
    return ListMyTicketsHandler(tickets, users)


def get_list_assigned_tickets_handler(
    tickets: TicketQueries = Depends(get_ticket_queries), users: UserQueries = Depends(get_user_queries)
) -> ListAssignedTicketsHandler:
    return ListAssignedTicketsHandler(tickets, users)


def get_list_all_tickets_handler(
    tickets: TicketQueries = Depends(get_ticket_queries), users: UserQueries = Depends(get_user_queries)
) -> ListAllTicketsHandler:
    return ListAllTicketsHandler(tickets, users)


def get_ticket_detail_handler(
    tickets: TicketQueries = Depends(get_ticket_queries), users: UserQueries = Depends(get_user_queries)
) -> GetTicketDetailHandler:
    return GetTicketDetailHandler(tickets, users, get_settings().ai_confidence_threshold)


def get_attachment_file_handler(
    tickets: TicketQueries = Depends(get_ticket_queries),
    users: UserQueries = Depends(get_user_queries),
    storage: FileStorage = Depends(get_file_storage),
) -> GetAttachmentFileHandler:
    return GetAttachmentFileHandler(tickets, users, storage)


def get_inventory_report_handler(
    inventory: InventoryQueries = Depends(get_inventory_queries), users: UserQueries = Depends(get_user_queries)
) -> GetInventoryReportHandler:
    return GetInventoryReportHandler(inventory, users)


def get_list_devices_handler(
    inventory: InventoryQueries = Depends(get_inventory_queries), users: UserQueries = Depends(get_user_queries)
) -> ListDevicesHandler:
    return ListDevicesHandler(inventory, users)


def get_list_my_devices_handler(
    inventory: InventoryQueries = Depends(get_inventory_queries), users: UserQueries = Depends(get_user_queries)
) -> ListMyDevicesHandler:
    return ListMyDevicesHandler(inventory, users)


def get_device_handler(
    inventory: InventoryQueries = Depends(get_inventory_queries), users: UserQueries = Depends(get_user_queries)
) -> GetDeviceHandler:
    return GetDeviceHandler(inventory, users)


def get_maintenance_history_handler(
    inventory: InventoryQueries = Depends(get_inventory_queries), users: UserQueries = Depends(get_user_queries)
) -> GetMaintenanceHistoryHandler:
    return GetMaintenanceHistoryHandler(inventory, users)


def get_failure_statistics_handler(
    statistics: StatisticsQueries = Depends(get_statistics_queries), users: UserQueries = Depends(get_user_queries)
) -> GetFailureStatisticsHandler:
    return GetFailureStatisticsHandler(statistics, users, get_settings().ai_confidence_threshold)


def get_my_notifications_handler(
    notifications: NotificationQueries = Depends(get_notification_queries),
    users: UserQueries = Depends(get_user_queries),
) -> GetMyNotificationsHandler:
    return GetMyNotificationsHandler(notifications, users)


def get_mark_notifications_read_handler(
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> MarkNotificationsReadHandler:
    return MarkNotificationsReadHandler(uow)
