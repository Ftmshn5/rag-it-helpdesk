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

Elle yeniden kurma:  python -m app.infrastructure.db.projections
"""

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.clock import utc_now
from app.domain.enums import TicketModifier
from app.domain.ticket_behavior import TicketBehaviorFactory
from app.infrastructure.db.models import (
    AIResponseModel,
    DeviceModel,
    TicketAttachmentModel,
    TicketCommentModel,
    TicketModel,
    UserModel,
)
from app.infrastructure.db.read_models import TicketSummaryModel
from app.infrastructure.db.repositories import SqlAlchemyTicketRepository
from app.infrastructure.db.session import SessionLocal

logger = logging.getLogger(__name__)


class TicketSummaryProjector:
    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self.session_factory = session_factory

    def refresh(self, ticket_id: int) -> None:
        """Tek bir talebin özet satırını kaynaktan yeniden hesaplar."""
        with self.session_factory() as session:
            row = self._build_row(session, ticket_id)
            if row is None:
                session.execute(
                    delete(TicketSummaryModel).where(TicketSummaryModel.ticket_id == ticket_id)
                )
            else:
                statement = insert(TicketSummaryModel).values(**row)
                session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[TicketSummaryModel.ticket_id], set_=row
                    )
                )
            session.commit()

    def rebuild(self) -> int:
        """Tabloyu tamamen siler ve tüm talepler için yeniden üretir."""
        with self.session_factory() as session:
            session.execute(delete(TicketSummaryModel))
            ticket_ids = session.scalars(select(TicketModel.id)).all()
            for ticket_id in ticket_ids:
                session.add(TicketSummaryModel(**self._build_row(session, ticket_id)))
            session.commit()
            return len(ticket_ids)

    def _build_row(self, session: Session, ticket_id: int) -> dict[str, Any] | None:
        ticket = SqlAlchemyTicketRepository(session).get(ticket_id)
        if ticket is None:
            return None

        # Hesaplanan alanlar domain'den: Factory + Decorator (iş kuralı tek yerde)
        behavior = TicketBehaviorFactory.create(ticket)
        requester = session.get(UserModel, ticket.requester_id)
        assignee = session.get(UserModel, ticket.assignee_id) if ticket.assignee_id else None
        device = session.get(DeviceModel, ticket.device_id) if ticket.device_id else None
        ai_response = session.scalar(
            select(AIResponseModel).where(AIResponseModel.ticket_id == ticket_id)
        )

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
            "comment_count": self._count(session, TicketCommentModel, ticket_id),
            "attachment_count": self._count(session, TicketAttachmentModel, ticket_id),
            "created_at": ticket.created_at,
            "resolved_at": ticket.resolved_at,
            "refreshed_at": utc_now(),
        }

    @staticmethod
    def _count(session: Session, model, ticket_id: int) -> int:
        return session.scalar(
            select(func.count()).select_from(model).where(model.ticket_id == ticket_id)
        )


def rebuild_all(session_factory: Callable[[], Session] = SessionLocal) -> None:
    count = TicketSummaryProjector(session_factory).rebuild()
    print(f"ticket_summary: {count} satır yeniden üretildi.")


if __name__ == "__main__":
    rebuild_all()
