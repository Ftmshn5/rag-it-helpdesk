"""Unit of Work'ün SQLAlchemy implementasyonu.

Her `with` bloğu yeni bir Session açar; tüm repository'ler bu aynı Session'ı
paylaştığı için yaptıkları değişiklikler tek transaction'da toplanır.
"""

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from app.application.interfaces.event_bus import EventBus
from app.application.interfaces.unit_of_work import UnitOfWork
from app.infrastructure.db.repositories import (
    SqlAlchemyAIResponseRepository,
    SqlAlchemyAssignmentRepository,
    SqlAlchemyDeviceRepository,
    SqlAlchemyMaintenanceRecordRepository,
    SqlAlchemyTicketAttachmentRepository,
    SqlAlchemyTicketCommentRepository,
    SqlAlchemyTicketRepository,
    SqlAlchemyUserNotificationRepository,
    SqlAlchemyUserRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Unit of Work deseni — SQLAlchemy implementasyonu (Template Method: _commit/_rollback)."""

    def __init__(self, event_bus: EventBus, session_factory: Callable[[], Session]) -> None:
        super().__init__(event_bus)
        self._session_factory = session_factory

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self.users = SqlAlchemyUserRepository(self._session)
        self.devices = SqlAlchemyDeviceRepository(self._session)
        self.assignments = SqlAlchemyAssignmentRepository(self._session)
        self.maintenance_records = SqlAlchemyMaintenanceRecordRepository(self._session)
        self.tickets = SqlAlchemyTicketRepository(self._session)
        self.ticket_attachments = SqlAlchemyTicketAttachmentRepository(self._session)
        self.ticket_comments = SqlAlchemyTicketCommentRepository(self._session)
        self.ai_responses = SqlAlchemyAIResponseRepository(self._session)
        self.notifications = SqlAlchemyUserNotificationRepository(self._session)
        return super().__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        super().__exit__(exc_type, exc_value, traceback)
        self._session.close()

    def _commit(self) -> None:
        self._session.commit()

    def _rollback(self) -> None:
        self._session.rollback()
