"""Projektörler: write tablolarından read model satırlarını üretir.

Yaklaşım: "olay → ilgili satırı kaynaktan yeniden hesapla".
Olay yalnızca HANGİ kaydın değiştiğini söyler (örn. ticket_id); satırın
içeriği her seferinde write tablolarından baştan hesaplanıp yazılır (upsert).

Neden olayın taşıdığı veriyle parça parça güncellemiyoruz?
- Sıra önemsizleşir: olaylar hangi sırayla gelirse gelsin sonuç aynıdır.
- Kendini onarır: bir olay kaçırılsa (dinleyici hata verse) bir sonraki
  olay satırı yine doğru hale getirir.
- Yeniden kurulabilir: aynı fonksiyon tüm tabloyu sıfırdan inşa eder
  (`rebuild`). Seed verisi gibi olay üretmeden eklenen kayıtlar için de gerekli.
Bedeli her olayda birkaç küçük sorgu çalışmasıdır; bu ölçekte önemsizdir.

refresh/rebuild akışı her projektörde aynıdır (Template Method: Projector);
alt sınıflar yalnızca hangi kayıtların ve satırın nasıl hesaplanacağını tanımlar.

Elle yeniden kurma:  python -m app.infrastructure.db.projections
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.clock import utc_now
from app.domain.enums import TicketModifier
from app.domain.ticket_behavior import TicketComponentFactory
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
from app.infrastructure.db.read_models import DeviceInventoryModel, TicketSummaryModel
from app.infrastructure.db.repositories import SqlAlchemyTicketRepository
from app.infrastructure.db.session import SessionLocal


class Projector(ABC):
    read_model: type[Base]
    key_column: str  # read model'in birincil anahtarı (örn. "ticket_id")

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self.session_factory = session_factory

    def refresh(self, key: int) -> None:
        """Tek bir kaydın satırını kaynaktan yeniden hesaplar (upsert ya da silme)."""
        with self.session_factory() as session:
            row = self.build_row(session, key)
            if row is None:  # kaynak kayıt silinmiş
                session.execute(
                    delete(self.read_model).where(getattr(self.read_model, self.key_column) == key)
                )
            else:
                statement = insert(self.read_model).values(**row)
                session.execute(
                    statement.on_conflict_do_update(index_elements=[self.key_column], set_=row)
                )
            session.commit()

    def rebuild(self) -> int:
        """Tabloyu tamamen siler ve tüm kayıtlar için yeniden üretir."""
        with self.session_factory() as session:
            session.execute(delete(self.read_model))
            keys = self.all_keys(session)
            for key in keys:
                session.add(self.read_model(**self.build_row(session, key)))
            session.commit()
            return len(keys)

    @abstractmethod
    def all_keys(self, session: Session) -> list[int]: ...

    @abstractmethod
    def build_row(self, session: Session, key: int) -> dict[str, Any] | None: ...


def count_where(session: Session, model, **filters) -> int:
    statement = select(func.count()).select_from(model).filter_by(**filters)
    return session.scalar(statement)


class TicketSummaryProjector(Projector):
    read_model = TicketSummaryModel
    key_column = "ticket_id"

    def all_keys(self, session: Session) -> list[int]:
        return list(session.scalars(select(TicketModel.id)))

    def build_row(self, session: Session, key: int) -> dict[str, Any] | None:
        ticket = SqlAlchemyTicketRepository(session).get(key)
        if ticket is None:
            return None

        # Hesaplanan alanlar domain'den: Factory + Decorator (iş kuralı tek yerde)
        behavior = TicketComponentFactory.create(ticket)
        requester = session.get(UserModel, ticket.requester_id)
        assignee = session.get(UserModel, ticket.assignee_id) if ticket.assignee_id else None
        device = session.get(DeviceModel, ticket.device_id) if ticket.device_id else None
        ai_response = session.scalar(select(AIResponseModel).where(AIResponseModel.ticket_id == key))

        return {
            "ticket_id": ticket.id,
            "title": ticket.title,
            "category": ticket.category.value,
            "status": ticket.status.value,
            "requester_id": ticket.requester_id,
            "requester_name": requester.full_name,
            "assignee_id": ticket.assignee_id,
            "assignee_name": assignee.full_name if assignee else None,
            "device_id": ticket.device_id,
            "device_asset_tag": device.asset_tag if device else None,
            "is_vip": TicketModifier.VIP in ticket.modifiers,
            "is_urgent": ticket.is_urgent,
            "sla_hours": behavior.sla_hours(),
            "priority_score": behavior.priority_score(),
            "due_at": ticket.created_at + timedelta(hours=behavior.sla_hours()),
            "ai_confidence": ai_response.confidence if ai_response else None,
            "ai_feedback": ai_response.user_feedback.value
            if ai_response and ai_response.user_feedback
            else None,
            "comment_count": count_where(session, TicketCommentModel, ticket_id=key),
            "attachment_count": count_where(session, TicketAttachmentModel, ticket_id=key),
            "created_at": ticket.created_at,
            "resolved_at": ticket.resolved_at,
            "refreshed_at": utc_now(),
        }


class DeviceInventoryProjector(Projector):
    read_model = DeviceInventoryModel
    key_column = "device_id"

    def all_keys(self, session: Session) -> list[int]:
        return list(session.scalars(select(DeviceModel.id)))

    def build_row(self, session: Session, key: int) -> dict[str, Any] | None:
        device = session.get(DeviceModel, key)
        if device is None:
            return None

        active = session.scalar(
            select(AssignmentModel).where(
                AssignmentModel.device_id == key, AssignmentModel.returned_at.is_(None)
            )
        )
        holder = session.get(UserModel, active.user_id) if active else None
        last_maintenance_at = session.scalar(
            select(func.max(MaintenanceRecordModel.performed_at)).where(
                MaintenanceRecordModel.device_id == key
            )
        )

        return {
            "device_id": device.id,
            "asset_tag": device.asset_tag,
            "type": device.type,
            "brand": device.brand,
            "model": device.model,
            "serial_number": device.serial_number,
            "status": device.status.value,
            "location": device.location,
            "purchase_date": device.purchase_date,
            "holder_id": holder.id if holder else None,
            "holder_name": holder.full_name if holder else None,
            "holder_department": holder.department if holder else None,
            "assigned_at": active.assigned_at if active else None,
            "has_open_maintenance": count_where(
                session, MaintenanceRecordModel, device_id=key, completed_at=None
            )
            > 0,
            "maintenance_count": count_where(session, MaintenanceRecordModel, device_id=key),
            "last_maintenance_at": last_maintenance_at,
            "refreshed_at": utc_now(),
        }


def rebuild_all(session_factory: Callable[[], Session] = SessionLocal) -> None:
    for projector_class in (TicketSummaryProjector, DeviceInventoryProjector):
        count = projector_class(session_factory).rebuild()
        print(f"{projector_class.read_model.__tablename__}: {count} satır yeniden üretildi.")


if __name__ == "__main__":
    rebuild_all()
