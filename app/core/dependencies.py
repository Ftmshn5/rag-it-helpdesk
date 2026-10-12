"""Bağımlılık enjeksiyonu (Dependency Injection) — uygulamanın "composition root"u.

Hangi arayüzün hangi somut sınıfla karşılanacağına yalnızca burada karar verilir
(UnitOfWork → SqlAlchemyUnitOfWork, EventBus → InMemoryEventBus). API katmanı
ihtiyaç duyduğu şeyleri FastAPI `Depends` ile buradan alır; somut sınıfları
kendisi oluşturmaz. Testlerde bu fonksiyonlar `app.dependency_overrides` ile
sahteleriyle değiştirilebilir.
"""

from collections.abc import Iterator

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
from app.application.queries.tickets import (
    GetTicketDetailHandler,
    ListAllTicketsHandler,
    ListAssignedTicketsHandler,
    ListMyTicketsHandler,
    TicketQueries,
)
from app.application.queries.users import ListUsersHandler, UserQueries
from app.core.config import get_settings
from app.core.event_subscriptions import register_subscribers
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.db.projections import TicketSummaryProjector
from app.infrastructure.db.queries import SqlTicketQueries, SqlUserQueries
from app.infrastructure.db.session import check_database_connection, get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from app.infrastructure.storage.local_file_storage import LocalFileStorage


def get_ai_support() -> AiSupportFacade:
    # Gerçek RAG hazır olduğunda (11. adım) yalnızca bu satır değişir.
    return FakeAiSupport()


def create_event_bus() -> EventBus:
    """Uygulama açılışında bir kez çağrılır; dinleyiciler burada kaydedilir."""
    event_bus = InMemoryEventBus()
    register_subscribers(
        event_bus,
        make_auto_answer_handler=lambda: AutoAnswerTicketHandler(
            SqlAlchemyUnitOfWork(event_bus),
            get_ai_support(),
            get_settings().ai_confidence_threshold,
        ),
        ticket_summary_projector=TicketSummaryProjector(),
    )
    return event_bus


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
