"""Unit of Work'ün SQLAlchemy implementasyonu.

Her `with` bloğu yeni bir Session açar; tüm repository'ler bu aynı Session'ı
paylaştığı için yaptıkları değişiklikler tek transaction'da toplanır.
"""

from collections.abc import Callable
from typing import Self

from sqlalchemy.orm import Session

from app.application.interfaces.event_bus import EventBus
from app.application.interfaces.unit_of_work import UnitOfWork
from app.infrastructure.db.repositories import (
    SqlAlchemyAssignmentRepository,
    SqlAlchemyDeviceRepository,
    SqlAlchemyMaintenanceRecordRepository,
    SqlAlchemyTicketRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.db.session import SessionLocal


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(
        self,
        event_bus: EventBus,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        super().__init__(event_bus)
        self.session_factory = session_factory

    def __enter__(self) -> Self:
        self.session = self.session_factory()
        self.users = SqlAlchemyUserRepository(self.session)
        self.devices = SqlAlchemyDeviceRepository(self.session)
        self.assignments = SqlAlchemyAssignmentRepository(self.session)
        self.maintenance_records = SqlAlchemyMaintenanceRecordRepository(self.session)
        self.tickets = SqlAlchemyTicketRepository(self.session)
        return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        super().__exit__(exc_type, exc_value, traceback)
        self.session.close()

    def _commit(self) -> None:
        self.session.commit()

    def _rollback(self) -> None:
        self.session.rollback()
