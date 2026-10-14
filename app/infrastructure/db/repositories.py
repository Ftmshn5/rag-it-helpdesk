"""Repository arayüzlerinin SQLAlchemy implementasyonları.

Repository deseni: command handler'lar veritabanını değil, application
katmanındaki repository arayüzlerini bilir. Ortak işlemler (get / add / update)
SqlAlchemyRepository tabanında bir kez yazılır (kalıtım); alt sınıflar yalnızca
hangi modelle ve hangi mapper'la çalışacaklarını ve kendilerine özgü sorguları
tanımlar. Domain nesnesi ↔ ORM modeli çevirisi mapper sınıflarındadır (mappers.py).
"""

from typing import Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.application.interfaces.repositories import (
    AIResponseRepository,
    AssignmentRepository,
    DeviceRepository,
    MaintenanceRecordRepository,
    TicketAttachmentRepository,
    TicketCommentRepository,
    TicketRepository,
    UserNotificationRepository,
    UserRepository,
)
from app.domain.entity import Entity
from app.domain.enums import UserRole
from app.domain.inventory import Assignment, Device, MaintenanceRecord
from app.domain.notifications import UserNotification
from app.domain.ticket import AIResponse, Ticket, TicketAttachment, TicketComment
from app.domain.user import User
from app.infrastructure.db.base import Base
from app.infrastructure.db.mappers import (
    AIResponseMapper,
    AssignmentMapper,
    DeviceMapper,
    MaintenanceRecordMapper,
    Mapper,
    TicketAttachmentMapper,
    TicketCommentMapper,
    TicketMapper,
    UserMapper,
    UserNotificationMapper,
)
from app.infrastructure.db.models import (
    AIResponseModel,
    AssignmentModel,
    DeviceModel,
    MaintenanceRecordModel,
    NotificationModel,
    TicketAttachmentModel,
    TicketCommentModel,
    TicketModel,
    UserModel,
)

E = TypeVar("E", bound=Entity)
M = TypeVar("M", bound=Base)


class EntityNotFoundError(Exception):
    """Güncellenmek istenen kayıt veritabanında yok (programlama hatası; kullanıcıya gösterilmez)."""


class SqlAlchemyRepository(Generic[E, M]):
    """Repository deseni — ortak SQLAlchemy implementasyonu.

    Alt sınıflar `model_class` ve `mapper` sınıf özelliklerini tanımlar.
    """

    model_class: type[M]
    mapper: Mapper[E, M]

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, entity_id: int) -> E | None:
        model = self._session.get(self.model_class, entity_id)
        return self.mapper.to_entity(model) if model else None

    def add(self, entity: E) -> E:
        model = self.model_class(**self.mapper.to_values(entity))
        self._session.add(model)
        # flush: INSERT'i hemen gönderir ki veritabanının verdiği id'yi alabilelim.
        # Kalıcı hale gelmesi yine de Unit of Work'ün commit'ine bağlıdır.
        self._session.flush()
        return entity.bind_id(model.id)

    def update(self, entity: E) -> None:
        model = self._session.get(self.model_class, entity.id)
        if model is None:
            raise EntityNotFoundError(f"{self.model_class.__name__} id={entity.id} bulunamadı")
        for column, value in self.mapper.to_values(entity).items():
            setattr(model, column, value)
        self._session.flush()

    def _first(self, statement: Select[tuple[M]]) -> E | None:
        model = self._session.scalars(statement).first()
        return self.mapper.to_entity(model) if model else None

    def _all(self, statement: Select[tuple[M]]) -> list[E]:
        return [self.mapper.to_entity(model) for model in self._session.scalars(statement)]


class SqlAlchemyUserRepository(SqlAlchemyRepository[User, UserModel], UserRepository):
    model_class = UserModel
    mapper = UserMapper()

    def list_by_role(self, role: UserRole) -> list[User]:
        return self._all(select(UserModel).where(UserModel.role == role).order_by(UserModel.id))


class SqlAlchemyDeviceRepository(SqlAlchemyRepository[Device, DeviceModel], DeviceRepository):
    model_class = DeviceModel
    mapper = DeviceMapper()

    def get_by_asset_tag(self, asset_tag: str) -> Device | None:
        return self._first(select(DeviceModel).where(DeviceModel.asset_tag == asset_tag))

    def get_by_serial_number(self, serial_number: str) -> Device | None:
        return self._first(select(DeviceModel).where(DeviceModel.serial_number == serial_number))


class SqlAlchemyAssignmentRepository(SqlAlchemyRepository[Assignment, AssignmentModel], AssignmentRepository):
    model_class = AssignmentModel
    mapper = AssignmentMapper()

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
    model_class = MaintenanceRecordModel
    mapper = MaintenanceRecordMapper()

    def get_open_for_device(self, device_id: int) -> MaintenanceRecord | None:
        return self._first(
            select(MaintenanceRecordModel).where(
                MaintenanceRecordModel.device_id == device_id,
                MaintenanceRecordModel.completed_at.is_(None),
            )
        )


class SqlAlchemyTicketRepository(SqlAlchemyRepository[Ticket, TicketModel], TicketRepository):
    model_class = TicketModel
    mapper = TicketMapper()


class SqlAlchemyTicketAttachmentRepository(
    SqlAlchemyRepository[TicketAttachment, TicketAttachmentModel], TicketAttachmentRepository
):
    model_class = TicketAttachmentModel
    mapper = TicketAttachmentMapper()


class SqlAlchemyTicketCommentRepository(
    SqlAlchemyRepository[TicketComment, TicketCommentModel], TicketCommentRepository
):
    model_class = TicketCommentModel
    mapper = TicketCommentMapper()


class SqlAlchemyAIResponseRepository(SqlAlchemyRepository[AIResponse, AIResponseModel], AIResponseRepository):
    model_class = AIResponseModel
    mapper = AIResponseMapper()

    def get_by_ticket(self, ticket_id: int) -> AIResponse | None:
        return self._first(select(AIResponseModel).where(AIResponseModel.ticket_id == ticket_id))


class SqlAlchemyUserNotificationRepository(
    SqlAlchemyRepository[UserNotification, NotificationModel], UserNotificationRepository
):
    model_class = NotificationModel
    mapper = UserNotificationMapper()

    def list_unread_for(self, recipient_id: int) -> list[UserNotification]:
        return self._all(
            select(NotificationModel).where(
                NotificationModel.recipient_id == recipient_id, NotificationModel.read_at.is_(None)
            )
        )
