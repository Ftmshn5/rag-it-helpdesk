"""CQRS okuma tarafının denormalize tabloları (read şeması).

Yazma tablolarından farklı olarak:
- Normalize değildir: talep sahibinin adı, cihazın demirbaş numarası gibi
  başka tablolardaki bilgiler de satırın içine kopyalanır (JOIN gerekmez).
- Hesaplanmış alanlar içerir: SLA, öncelik puanı, son tarih (Decorator'dan).
- Yabancı anahtar ve iş kuralı kısıtı yoktur; doğruluğun kaynağı write
  tablolarıdır, bu tablolar onlardan türetilir ve her an yeniden kurulabilir.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base

READ_SCHEMA = "read"


class TicketSummaryModel(Base):
    """Talep listelerinin (UC-03 taleplerim, UC-05 atanan talepler) kaynağı."""

    __tablename__ = "ticket_summary"
    __table_args__ = {"schema": READ_SCHEMA}

    ticket_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)

    requester_id: Mapped[int] = mapped_column(Integer, index=True)
    requester_name: Mapped[str] = mapped_column(String(120))
    assignee_id: Mapped[int | None] = mapped_column(Integer, index=True)
    assignee_name: Mapped[str | None] = mapped_column(String(120))
    device_id: Mapped[int | None] = mapped_column(Integer)
    device_asset_tag: Mapped[str | None] = mapped_column(String(50))

    # Decorator'lı nesneden hesaplanan alanlar
    is_vip: Mapped[bool] = mapped_column(Boolean)
    is_urgent: Mapped[bool] = mapped_column(Boolean)
    sla_hours: Mapped[int] = mapped_column(Integer)
    priority_score: Mapped[int] = mapped_column(Integer)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_feedback: Mapped[str | None] = mapped_column(String(32))
    comment_count: Mapped[int] = mapped_column(Integer)
    attachment_count: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
