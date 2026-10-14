"""Yazma tarafının (write şeması) SQLAlchemy modelleri.

Bunlar domain varlıklarının veritabanı karşılıklarıdır. Domain sınıflarıyla
karışmasın diye hepsi "Model" son ekiyle adlandırıldı; ikisi arasındaki
dönüşümü repository'ler yapacak.
"""

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    AiFeedback,
    DeviceStatus,
    MaintenanceType,
    SupportLevel,
    TicketCategory,
    TicketModifier,
    TicketStatus,
    UserRole,
)
from app.infrastructure.db.base import Base

# bge-m3 (Ollama) embedding modelinin vektör boyutu; model değişirse migration gerekir.
# Uygulama açılışında embedding sağlayıcısına da bu değer verilir: model farklı
# boyutta vektör döndürürse veritabanına yazmadan önce hata verilir.
EMBEDDING_DIMENSION = 1024


class ColumnFactory:
    """Model tanımlarında tekrar eden sütun tiplerini üretir."""

    @staticmethod
    def enum(enum_class: type, name: str) -> Enum:
        """Enum'u PostgreSQL native ENUM yerine VARCHAR olarak saklar.

        Native ENUM'a yeni değer eklemek migration'da zahmetlidir; VARCHAR + CHECK
        kısıtında ise kısıtı yeniden tanımlamak yeterlidir. CHECK sayesinde
        veritabanı geçersiz değerleri yine reddeder.

        `name` CHECK kısıtının adında kullanılır (örn. ck_devices_status); aynı enum
        bir tabloda birden fazla sütunda kullanılabildiği için sütun adı verilir.
        """
        return Enum(enum_class, name=name, native_enum=False, length=32, create_constraint=True)

    @staticmethod
    def created_at() -> Mapped[datetime]:
        return mapped_column(DateTime(timezone=True), server_default=func.now())


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    role: Mapped[UserRole] = mapped_column(ColumnFactory.enum(UserRole, "role"))
    department: Mapped[str | None] = mapped_column(String(120))
    is_vip: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Yalnızca teknisyenlerde dolu (TIER_1 / TIER_2); diğer rollerde boş
    support_level: Mapped[SupportLevel | None] = mapped_column(ColumnFactory.enum(SupportLevel, "support_level"))


class DeviceModel(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_tag: Mapped[str] = mapped_column(String(50), unique=True)
    type: Mapped[str] = mapped_column(String(50))
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    serial_number: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[DeviceStatus] = mapped_column(ColumnFactory.enum(DeviceStatus, "status"))
    location: Mapped[str | None] = mapped_column(String(120))
    purchase_date: Mapped[date | None] = mapped_column(Date)


class AssignmentModel(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        # İş kuralı 1'in veritabanı güvencesi: bir cihazın returned_at'i boş
        # (aktif) olan en fazla bir zimmeti olabilir. Asıl kontrol command
        # handler'da yapılır; bu indeks ikinci savunma hattıdır.
        Index(
            "uq_assignments_active_device",
            "device_id",
            unique=True,
            postgresql_where=text("returned_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = ColumnFactory.created_at()
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


ALLOWED_MODIFIERS_SQL = ", ".join(f"'{modifier.value}'" for modifier in TicketModifier)


class TicketModel(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        # Dizideki her eleman geçerli bir modifier olmalı ("<@" = soldaki dizi sağdakinin alt kümesi)
        CheckConstraint(
            f"modifiers <@ ARRAY[{ALLOWED_MODIFIERS_SQL}]::varchar[]",
            name="modifiers",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[TicketCategory] = mapped_column(ColumnFactory.enum(TicketCategory, "category"))
    status: Mapped[TicketStatus] = mapped_column(ColumnFactory.enum(TicketStatus, "status"), index=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"))
    # Decorator'lar değil, yalnızca adları saklanır; Factory okurken nesneyi sarar
    modifiers: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), server_default=text("'{}'")
    )
    support_level: Mapped[SupportLevel] = mapped_column(
        ColumnFactory.enum(SupportLevel, "support_level"), server_default=SupportLevel.AI.value
    )
    created_at: Mapped[datetime] = ColumnFactory.created_at()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MaintenanceRecordModel(Base):
    __tablename__ = "maintenance_records"
    __table_args__ = (
        # Bir cihazda aynı anda tek açık bakım: aksi halde "önceki durum"
        # (previous_device_status) hangi kayda göre geri yükleneceği belirsizleşir.
        Index(
            "uq_maintenance_records_open_device",
            "device_id",
            unique=True,
            postgresql_where=text("completed_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    technician_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"))
    type: Mapped[MaintenanceType] = mapped_column(ColumnFactory.enum(MaintenanceType, "type"))
    description: Mapped[str] = mapped_column(Text)
    previous_device_status: Mapped[DeviceStatus] = mapped_column(
        ColumnFactory.enum(DeviceStatus, "previous_device_status")
    )
    performed_at: Mapped[datetime] = ColumnFactory.created_at()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TicketAttachmentModel(Base):
    __tablename__ = "ticket_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(50))
    uploaded_at: Mapped[datetime] = ColumnFactory.created_at()


class TicketCommentModel(Base):
    __tablename__ = "ticket_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = ColumnFactory.created_at()


class AIResponseModel(Base):
    __tablename__ = "ai_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique: bir ticket'ın en fazla bir AI yanıtı olur (ER diyagramında 1 - 0..1)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), unique=True
    )
    answer: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    sources: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    user_feedback: Mapped[AiFeedback | None] = mapped_column(ColumnFactory.enum(AiFeedback, "user_feedback"))


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    file_path: Mapped[str] = mapped_column(String(500))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSION))

    __table_args__ = (
        # Kosinüs uzaklığıyla (<=>) en yakın parçaları bulmak için yaklaşık komşu indeksi
        Index(
            "ix_knowledge_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
