"""Bağımlılık enjeksiyonu (Dependency Injection) — uygulamanın "composition root"u.

Hangi arayüzün hangi somut sınıfla karşılanacağına yalnızca burada karar verilir
(UnitOfWork → SqlAlchemyUnitOfWork, EventBus → InMemoryEventBus). API katmanı
ihtiyaç duyduğu şeyleri FastAPI `Depends` ile buradan alır; somut sınıfları
kendisi oluşturmaz. Testlerde bu fonksiyonlar `app.dependency_overrides` ile
sahteleriyle değiştirilebilir.
"""

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.application.commands.ai_answers import AutoAnswerTicketHandler, EvaluateAiAnswerHandler
from app.application.commands.attachments import AttachScreenshotHandler
from app.application.commands.assignments import AssignDeviceHandler, ReturnDeviceHandler
from app.application.commands.devices import (
    RegisterDeviceHandler,
    RetireDeviceHandler,
    UpdateDeviceDetailsHandler,
)
from app.application.commands.maintenance import (
    CompleteMaintenanceHandler,
    StartMaintenanceHandler,
)
from app.application.commands.ticket_workflow import (
    AddCommentHandler,
    AssignTicketHandler,
    CloseTicketHandler,
    ReopenTicketHandler,
    ResolveTicketHandler,
    StartWorkHandler,
)
from app.application.commands.tickets import CreateTicketHandler, SetTicketUrgencyHandler
from app.application.errors import AuthenticationError
from app.application.interfaces.ai_support import AiSupportFacade
from app.application.interfaces.event_bus import EventBus
from app.application.interfaces.file_storage import FileStorage
from app.application.interfaces.unit_of_work import UnitOfWork
from app.application.queries.inventory import (
    GetInventoryReportHandler,
    GetMaintenanceHistoryHandler,
    InventoryQueries,
    ListDevicesHandler,
    ListMyDevicesHandler,
)
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
from app.core.event_subscriptions import register_subscribers, submit_auto_answer
from app.domain.enums import TicketStatus
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.ai.ollama import OllamaChatModel, OllamaEmbeddingProvider
from app.infrastructure.ai.rag_ai_support import RagAiSupport, SimilarityConfidence
from app.infrastructure.ai.retriever import PgVectorRetriever
from app.infrastructure.db.models import EMBEDDING_DIMENSION
from app.infrastructure.db.projections import DeviceInventoryProjector, TicketSummaryProjector
from app.infrastructure.db.queries import SqlInventoryQueries, SqlTicketQueries, SqlUserQueries
from app.infrastructure.db.session import SessionLocal, check_database_connection, get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from app.infrastructure.events.task_runner import TaskRunner
from app.infrastructure.storage.local_file_storage import LocalFileStorage


@lru_cache
def get_ai_support() -> AiSupportFacade:
    """AI implementasyonunu seçen tek yer (AI_PROVIDER ayarı).

    Facade'ın faydası burada görünür: sahte AI'dan gerçek RAG'e geçmek için
    application ve domain katmanında hiçbir şey değişmez, yalnızca bu fonksiyon.
    Strategy'ler (Ollama embedding / chat) de burada seçilir. Nesneler durum
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
        retriever=PgVectorRetriever(SessionLocal),
        chat_model=OllamaChatModel(
            settings.ollama_base_url,
            settings.llm_model,
            timeout_seconds=settings.ollama_timeout_seconds,
            max_tokens=settings.llm_max_tokens,
        ),
        confidence=SimilarityConfidence(
            floor=settings.rag_similarity_floor, ceiling=settings.rag_similarity_ceiling
        ),
        top_k=settings.rag_top_k,
    )


def make_auto_answer_handler(event_bus: EventBus) -> AutoAnswerTicketHandler:
    return AutoAnswerTicketHandler(
        SqlAlchemyUnitOfWork(event_bus), get_ai_support(), get_settings().ai_confidence_threshold
    )


def create_event_bus(task_runner: TaskRunner | None = None) -> EventBus:
    """Uygulama açılışında bir kez çağrılır; dinleyiciler burada kaydedilir."""
    event_bus = InMemoryEventBus()
    register_subscribers(
        event_bus,
        make_auto_answer_handler=lambda: make_auto_answer_handler(event_bus),
        ticket_summary_projector=TicketSummaryProjector(),
        device_inventory_projector=DeviceInventoryProjector(),
        task_runner=task_runner,
    )
    return event_bus


def resume_pending_auto_answers(event_bus: EventBus, task_runner: TaskRunner) -> int:
    """Açılışta, AI yanıtı bekleyen (OPEN) talepleri yeniden kuyruğa alır.

    Arka plan kuyruğu bellekte tutulur; uygulama yeniden başlarsa (örn.
    --reload ile) bekleyen işler kaybolur ve talep OPEN'da kalırdı. Handler
    idempotent olduğu için bir talebin iki kez kuyruğa girmesi zararsızdır.
    """
    with SessionLocal() as session:
        pending = SqlTicketQueries(session).list_all(TicketStatus.OPEN)
    for ticket in pending:
        submit_auto_answer(task_runner, lambda: make_auto_answer_handler(event_bus), ticket.ticket_id)
    return len(pending)


def get_event_bus(request: Request) -> EventBus:
    # Tüm istekler aynı bus'ı paylaşır: abonelikler uygulama ömrü boyunca geçerli
    return request.app.state.event_bus


def get_unit_of_work(event_bus: EventBus = Depends(get_event_bus)) -> UnitOfWork:
    # Her istek kendi Unit of Work'ünü (dolayısıyla kendi transaction'ını) alır
    return SqlAlchemyUnitOfWork(event_bus)


def get_file_storage() -> FileStorage:
    return LocalFileStorage(get_settings().upload_dir)


def get_current_user_id(x_user_id: int | None = Header(default=None)) -> int:
    """İşlemi yapan kullanıcıyı X-User-Id başlığından alır.

    Gerçek kimlik doğrulama (şifre/token) kapsam dışı; kullanıcının var olup
    olmadığı ve rolü handler'larda kontrol edilir.
    """
    if x_user_id is None:
        raise AuthenticationError("X-User-Id başlığı gerekli.")
    return x_user_id


# --- Command handler'lar ---


def get_register_device_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return RegisterDeviceHandler(uow)


def get_update_device_details_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return UpdateDeviceDetailsHandler(uow)


def get_retire_device_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return RetireDeviceHandler(uow)


def get_assign_device_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return AssignDeviceHandler(uow)


def get_return_device_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return ReturnDeviceHandler(uow)


def get_start_maintenance_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return StartMaintenanceHandler(uow)


def get_complete_maintenance_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return CompleteMaintenanceHandler(uow)


def get_create_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return CreateTicketHandler(uow)


def get_set_ticket_urgency_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return SetTicketUrgencyHandler(uow)


def get_attach_screenshot_handler(
    uow: UnitOfWork = Depends(get_unit_of_work),
    storage: FileStorage = Depends(get_file_storage),
):
    return AttachScreenshotHandler(uow, storage, get_settings().max_upload_size_bytes)


def get_assign_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return AssignTicketHandler(uow)


def get_start_work_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return StartWorkHandler(uow)


def get_resolve_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return ResolveTicketHandler(uow)


def get_close_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return CloseTicketHandler(uow)


def get_reopen_ticket_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return ReopenTicketHandler(uow)


def get_add_comment_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return AddCommentHandler(uow)


def get_evaluate_ai_answer_handler(uow: UnitOfWork = Depends(get_unit_of_work)):
    return EvaluateAiAnswerHandler(uow)


# --- Okuma tarafı / altyapı ---


def get_db_session() -> Iterator[Session]:
    """Okuma tarafı (queries) için düz oturum; yazma işlemleri UnitOfWork kullanır."""
    yield from get_session()


def get_database_status() -> bool:
    return check_database_connection()


# --- Okuma tarafı (queries): Unit of Work yok, düz salt-okunur oturum ---


def get_ticket_queries(session: Session = Depends(get_db_session)) -> TicketQueries:
    return SqlTicketQueries(session)


def get_user_queries(session: Session = Depends(get_db_session)) -> UserQueries:
    return SqlUserQueries(session)


def get_list_users_handler(users: UserQueries = Depends(get_user_queries)):
    return ListUsersHandler(users)


def get_list_my_tickets_handler(
    tickets: TicketQueries = Depends(get_ticket_queries),
    users: UserQueries = Depends(get_user_queries),
):
    return ListMyTicketsHandler(tickets, users)


def get_list_assigned_tickets_handler(
    tickets: TicketQueries = Depends(get_ticket_queries),
    users: UserQueries = Depends(get_user_queries),
):
    return ListAssignedTicketsHandler(tickets, users)


def get_list_all_tickets_handler(
    tickets: TicketQueries = Depends(get_ticket_queries),
    users: UserQueries = Depends(get_user_queries),
):
    return ListAllTicketsHandler(tickets, users)


def get_ticket_detail_handler(
    tickets: TicketQueries = Depends(get_ticket_queries),
    users: UserQueries = Depends(get_user_queries),
):
    return GetTicketDetailHandler(tickets, users, get_settings().ai_confidence_threshold)


def get_inventory_queries(session: Session = Depends(get_db_session)) -> InventoryQueries:
    return SqlInventoryQueries(session)


def get_inventory_report_handler(
    inventory: InventoryQueries = Depends(get_inventory_queries),
    users: UserQueries = Depends(get_user_queries),
):
    return GetInventoryReportHandler(inventory, users)


def get_list_my_devices_handler(
    inventory: InventoryQueries = Depends(get_inventory_queries),
    users: UserQueries = Depends(get_user_queries),
):
    return ListMyDevicesHandler(inventory, users)


def get_maintenance_history_handler(
    inventory: InventoryQueries = Depends(get_inventory_queries),
    users: UserQueries = Depends(get_user_queries),
):
    return GetMaintenanceHistoryHandler(inventory, users)


def get_list_devices_handler(
    inventory: InventoryQueries = Depends(get_inventory_queries),
    users: UserQueries = Depends(get_user_queries),
):
    return ListDevicesHandler(inventory, users)


def get_attachment_file_handler(
    tickets: TicketQueries = Depends(get_ticket_queries),
    users: UserQueries = Depends(get_user_queries),
    storage: FileStorage = Depends(get_file_storage),
):
    return GetAttachmentFileHandler(tickets, users, storage)
