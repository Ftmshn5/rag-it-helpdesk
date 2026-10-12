"""Repository arayüzlerinin SQLAlchemy implementasyonları.

Domain varlıkları ile SQLAlchemy modelleri aynı alan adlarına sahip olduğu için
dönüşüm (mapping) ortak taban sınıfta alan adları üzerinden genel olarak yapılır.
Farklı dönüşüm gereken yerlerde (örn. Ticket.modifiers) alt sınıf bunu ezer.
"""

from dataclasses import fields
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.interfaces.repositories import (
    AssignmentRepository,
    DeviceRepository,
    MaintenanceRecordRepository,
    TicketRepository,
    UserRepository,
)
from app.domain.enums import TicketModifier
from app.domain.inventory import Assignment, Device, MaintenanceRecord
from app.domain.ticket import Ticket
from app.domain.user import User
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (
    AssignmentModel,
    DeviceModel,
    MaintenanceRecordModel,
    TicketModel,
    UserModel,
)

E = TypeVar("E")
M = TypeVar("M", bound=Base)


class EntityNotFoundError(Exception):
    pass


class SqlAlchemyRepository(Generic[E, M]):
    entity_class: type[E]
    model_class: type[M]

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Mapping (model <-> domain varlığı) ---

    def _to_entity(self, model: M) -> E:
        return self.entity_class(
            **{field.name: getattr(model, field.name) for field in fields(self.entity_class)}
        )

    def _to_model_values(self, entity: E) -> dict[str, Any]:
        return {field.name: getattr(entity, field.name) for field in fields(entity)}

    # --- Ortak işlemler ---

    def get(self, entity_id: int) -> E | None:
        model = self.session.get(self.model_class, entity_id)
        return self._to_entity(model) if model else None

    def add(self, entity: E) -> E:
        model = self.model_class(**self._to_model_values(entity))
        self.session.add(model)
        # flush: INSERT'i hemen gönderir ki veritabanının verdiği id'yi alabilelim.
        # Kalıcı hale gelmesi yine de Unit of Work'ün commit'ine bağlıdır.
        self.session.flush()
        entity.id = model.id
        return entity

    def update(self, entity: E) -> None:
        model = self.session.get(self.model_class, entity.id)
        if model is None:
            raise EntityNotFoundError(f"{self.model_class.__name__} id={entity.id} bulunamadı")
        for name, value in self._to_model_values(entity).items():
            setattr(model, name, value)
        self.session.flush()

    def _first(self, statement) -> E | None:
        model = self.session.scalars(statement).first()
        return self._to_entity(model) if model else None


class SqlAlchemyUserRepository(SqlAlchemyRepository[User, UserModel], UserRepository):
    entity_class = User
    model_class = UserModel


class SqlAlchemyDeviceRepository(SqlAlchemyRepository[Device, DeviceModel], DeviceRepository):
    entity_class = Device
    model_class = DeviceModel

    def get_by_asset_tag(self, asset_tag: str) -> Device | None:
        return self._first(select(DeviceModel).where(DeviceModel.asset_tag == asset_tag))


class SqlAlchemyAssignmentRepository(
    SqlAlchemyRepository[Assignment, AssignmentModel], AssignmentRepository
):
    entity_class = Assignment
    model_class = AssignmentModel

    def get_active_for_device(self, device_id: int) -> Assignment | None:
        return self._first(
            select(AssignmentModel).where(
                AssignmentModel.device_id == device_id,
                AssignmentModel.returned_at.is_(None),
            )
        )


class SqlAlchemyMaintenanceRecordRepository(
    SqlAlchemyRepository[MaintenanceRecord, MaintenanceRecordModel], MaintenanceRecordRepository
):
    entity_class = MaintenanceRecord
    model_class = MaintenanceRecordModel

    def get_open_for_device(self, device_id: int) -> MaintenanceRecord | None:
        return self._first(
            select(MaintenanceRecordModel).where(
                MaintenanceRecordModel.device_id == device_id,
                MaintenanceRecordModel.completed_at.is_(None),
            )
        )


class SqlAlchemyTicketRepository(SqlAlchemyRepository[Ticket, TicketModel], TicketRepository):
    entity_class = Ticket
    model_class = TicketModel

    def _to_entity(self, model: TicketModel) -> Ticket:
        ticket = super()._to_entity(model)
        # Veritabanında düz metin dizisi; domain'de enum listesi
        ticket.modifiers = [TicketModifier(value) for value in model.modifiers]
        return ticket
