"""Domain varlığı ↔ SQLAlchemy modeli dönüşümleri: Data Mapper deseni.

Domain sınıfları veritabanını bilmez, SQLAlchemy modelleri de iş kuralı içermez.
İkisi arasındaki çeviriyi her varlık için ayrı, küçük bir mapper sınıfı yapar:

- to_entity(model): veritabanı satırından domain nesnesini yeniden kurar
  (constructor'a tüm alanlar verilir; kurallar yeni nesne oluştururken değil,
  iş metotları çağrılırken uygulanır).
- to_values(entity): domain nesnesinin salt okunur özelliklerinden, modele
  yazılacak sütun değerlerini üretir.

Repository'ler hangi mapper'ı kullanacaklarını bilir (bkz. repositories.py);
domain tarafındaki alanlar korumalı olduğu için dönüşüm yalnızca public
okuma özellikleri ve constructor üzerinden yapılır.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from app.domain.entity import Entity
from app.domain.enums import TicketModifier
from app.domain.inventory import Assignment, Device, MaintenanceRecord
from app.domain.ticket import AIResponse, Ticket, TicketAttachment, TicketComment
from app.domain.user import User
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (
    AIResponseModel,
    AssignmentModel,
    DeviceModel,
    MaintenanceRecordModel,
    TicketAttachmentModel,
    TicketCommentModel,
    TicketModel,
    UserModel,
)

E = TypeVar("E", bound=Entity)
M = TypeVar("M", bound=Base)


class Mapper(ABC, Generic[E, M]):
    """Data Mapper deseni — soyut mapper: bir varlık türünü bir model türüne çevirir."""

    @abstractmethod
    def to_entity(self, model: M) -> E: ...

    @abstractmethod
    def to_values(self, entity: E) -> dict[str, Any]:
        """Modele yazılacak sütun değerleri (id hariç; kimliği veritabanı verir)."""


class UserMapper(Mapper[User, UserModel]):
    def to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            full_name=model.full_name,
            email=model.email,
            role=model.role,
            department=model.department,
            is_vip=model.is_vip,
            support_level=model.support_level,
        )

    def to_values(self, entity: User) -> dict[str, Any]:
        return {
            "full_name": entity.full_name,
            "email": entity.email,
            "role": entity.role,
            "department": entity.department,
            "is_vip": entity.is_vip,
            "support_level": entity.support_level,
        }


class DeviceMapper(Mapper[Device, DeviceModel]):
    def to_entity(self, model: DeviceModel) -> Device:
        return Device(
            id=model.id,
            asset_tag=model.asset_tag,
            type=model.type,
            brand=model.brand,
            model=model.model,
            serial_number=model.serial_number,
            status=model.status,
            location=model.location,
            purchase_date=model.purchase_date,
        )

    def to_values(self, entity: Device) -> dict[str, Any]:
        return {
            "asset_tag": entity.asset_tag,
            "type": entity.type,
            "brand": entity.brand,
            "model": entity.model,
            "serial_number": entity.serial_number,
            "status": entity.status,
            "location": entity.location,
            "purchase_date": entity.purchase_date,
        }


class AssignmentMapper(Mapper[Assignment, AssignmentModel]):
    def to_entity(self, model: AssignmentModel) -> Assignment:
        return Assignment(
            id=model.id,
            device_id=model.device_id,
            user_id=model.user_id,
            assigned_by=model.assigned_by,
            assigned_at=model.assigned_at,
            returned_at=model.returned_at,
        )

    def to_values(self, entity: Assignment) -> dict[str, Any]:
        return {
            "device_id": entity.device_id,
            "user_id": entity.user_id,
            "assigned_by": entity.assigned_by,
            "assigned_at": entity.assigned_at,
            "returned_at": entity.returned_at,
        }


class MaintenanceRecordMapper(Mapper[MaintenanceRecord, MaintenanceRecordModel]):
    def to_entity(self, model: MaintenanceRecordModel) -> MaintenanceRecord:
        return MaintenanceRecord(
            id=model.id,
            device_id=model.device_id,
            technician_id=model.technician_id,
            ticket_id=model.ticket_id,
            type=model.type,
            description=model.description,
            previous_device_status=model.previous_device_status,
            performed_at=model.performed_at,
            completed_at=model.completed_at,
        )

    def to_values(self, entity: MaintenanceRecord) -> dict[str, Any]:
        return {
            "device_id": entity.device_id,
            "technician_id": entity.technician_id,
            "ticket_id": entity.ticket_id,
            "type": entity.type,
            "description": entity.description,
            "previous_device_status": entity.previous_device_status,
            "performed_at": entity.performed_at,
            "completed_at": entity.completed_at,
        }


class TicketMapper(Mapper[Ticket, TicketModel]):
    def to_entity(self, model: TicketModel) -> Ticket:
        return Ticket(
            id=model.id,
            title=model.title,
            description=model.description,
            category=model.category,
            requester_id=model.requester_id,
            status=model.status,
            assignee_id=model.assignee_id,
            device_id=model.device_id,
            # Veritabanında düz metin dizisi; domain'de enum listesi
            modifiers=[TicketModifier(value) for value in model.modifiers],
            support_level=model.support_level,
            created_at=model.created_at,
            resolved_at=model.resolved_at,
        )

    def to_values(self, entity: Ticket) -> dict[str, Any]:
        return {
            "title": entity.title,
            "description": entity.description,
            "category": entity.category,
            "requester_id": entity.requester_id,
            "status": entity.status,
            "assignee_id": entity.assignee_id,
            "device_id": entity.device_id,
            "modifiers": [modifier.value for modifier in entity.modifiers],
            "support_level": entity.support_level,
            "created_at": entity.created_at,
            "resolved_at": entity.resolved_at,
        }


class TicketAttachmentMapper(Mapper[TicketAttachment, TicketAttachmentModel]):
    def to_entity(self, model: TicketAttachmentModel) -> TicketAttachment:
        return TicketAttachment(
            id=model.id,
            ticket_id=model.ticket_id,
            file_path=model.file_path,
            mime_type=model.mime_type,
            uploaded_at=model.uploaded_at,
        )

    def to_values(self, entity: TicketAttachment) -> dict[str, Any]:
        return {
            "ticket_id": entity.ticket_id,
            "file_path": entity.file_path,
            "mime_type": entity.mime_type,
            "uploaded_at": entity.uploaded_at,
        }


class TicketCommentMapper(Mapper[TicketComment, TicketCommentModel]):
    def to_entity(self, model: TicketCommentModel) -> TicketComment:
        return TicketComment(
            id=model.id,
            ticket_id=model.ticket_id,
            author_id=model.author_id,
            content=model.content,
            created_at=model.created_at,
        )

    def to_values(self, entity: TicketComment) -> dict[str, Any]:
        return {
            "ticket_id": entity.ticket_id,
            "author_id": entity.author_id,
            "content": entity.content,
            "created_at": entity.created_at,
        }


class AIResponseMapper(Mapper[AIResponse, AIResponseModel]):
    def to_entity(self, model: AIResponseModel) -> AIResponse:
        return AIResponse(
            id=model.id,
            ticket_id=model.ticket_id,
            answer=model.answer,
            confidence=model.confidence,
            sources=list(model.sources),
            user_feedback=model.user_feedback,
        )

    def to_values(self, entity: AIResponse) -> dict[str, Any]:
        return {
            "ticket_id": entity.ticket_id,
            "answer": entity.answer,
            "confidence": entity.confidence,
            "sources": entity.sources,
            "user_feedback": entity.user_feedback,
        }
