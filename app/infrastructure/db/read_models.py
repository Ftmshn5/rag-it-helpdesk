"""CQRS okuma tarafının denormalize tabloları (read şeması).

Yazma tablolarından farklı olarak:
- Normalize değildir: talep sahibinin adı, cihazın demirbaş numarası gibi
  başka tablolardaki bilgiler de satırın içine kopyalanır (JOIN gerekmez).
- Hesaplanmış alanlar içerir: SLA, öncelik puanı, son tarih (Decorator'dan).
- Yabancı anahtar ve iş kuralı kısıtı yoktur; doğruluğun kaynağı write
  tablolarıdır, bu tablolar onlardan türetilir ve her an yeniden kurulabilir.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
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
    support_level: Mapped[str] = mapped_column(String(32))

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
    # Decorator zincirinin katmanları: [{"name", "sla_hours", "priority_score"}, …] (en içten dışa)
    sla_layers: Mapped[list[dict]] = mapped_column(JSONB)

    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_feedback: Mapped[str | None] = mapped_column(String(32))
    comment_count: Mapped[int] = mapped_column(Integer)
    attachment_count: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TicketTimelineModel(Base):
    """Talep zaman çizelgesi (E3): her satır yayınlanmış bir olaydır (yalnızca eklenir).

    Diğer read model'lerden farkı: satırlar write tablolarından yeniden hesaplanamaz,
    çünkü durum geçmişi yalnızca olaylarda vardır. Bu yüzden tablo olaylarla büyür
    ve "yeniden kur" onu silmez (bkz. TicketTimelineProjector).
    """

    __tablename__ = "ticket_timeline"
    __table_args__ = (
        Index("ix_ticket_timeline_ticket_occurred", "ticket_id", "occurred_at"),
        {"schema": READ_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[int | None] = mapped_column(Integer)
    actor_name: Mapped[str | None] = mapped_column(String(120))  # yazıldığı andaki ad (denormalize)
    details: Mapped[dict] = mapped_column(JSONB)  # türe özgü bilgiler (örn. eski/yeni durum, güven)


class DeviceInventoryModel(Base):
    """Envanter raporunun (UC-11) ve "zimmetli cihazlarım"ın (UC-04) kaynağı.

    Bir cihazın kimde olduğu (zimmet tablosu) ve bakım özeti (bakım tablosu)
    satırın içine kopyalanır; rapor tek tablodan, JOIN'siz okunur.
    """

    __tablename__ = "device_inventory"
    __table_args__ = {"schema": READ_SCHEMA}

    device_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    asset_tag: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(50), index=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    serial_number: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32), index=True)
    location: Mapped[str | None] = mapped_column(String(120))
    purchase_date: Mapped[date | None] = mapped_column(Date)

    # Aktif zimmet (zimmet tablosundan)
    holder_id: Mapped[int | None] = mapped_column(Integer, index=True)
    holder_name: Mapped[str | None] = mapped_column(String(120))
    holder_department: Mapped[str | None] = mapped_column(String(120))
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Bakım özeti (bakım tablosundan)
    has_open_maintenance: Mapped[bool] = mapped_column(Boolean)
    maintenance_count: Mapped[int] = mapped_column(Integer)
    last_maintenance_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
