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

Projektörler aynı zamanda olay dinleyicisidir (Observer: EventHandler): hangi
olaylara abone olacaklarını `source_events`, olaydan hangi kaydın etkilendiğini
`key_of` ile kendileri bildirir. Yeni bir read model eklemek abonelik kodunu
değiştirmez.

İstisna — zaman çizelgesi (TicketTimelineProjector): durum geçmişi write
tablolarında saklanmadığı, yalnızca olaylarda bulunduğu için satırlar olaydan
EKLENİR (yalnızca eklenir, yeniden hesaplanmaz). Bu yüzden "yeniden kur" onu
silmez; yalnızca hiç kaydı olmayan talepler için bilinenleri doldurur.

Elle yeniden kurma:  python -m app.infrastructure.db.projections
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.application.interfaces.event_bus import EventHandler
from app.application.queries.tickets import TimelineEntryKind
from app.domain.clock import Clock
from app.domain.enums import TicketModifier
from app.domain.events import (
    AiAnswerRecorded,
    AiFeedbackGiven,
    DeviceAssigned,
    DeviceDetailsUpdated,
    DeviceEvent,
    DeviceRegistered,
    DeviceRetired,
    DeviceReturned,
    DomainEvent,
    MaintenanceCompleted,
    MaintenanceStarted,
    ScreenshotAttached,
    TicketCommentAdded,
    TicketCreated,
    TicketEvent,
    TicketStatusChanged,
    TicketUrgencyChanged,
)
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
from app.infrastructure.db.read_models import DeviceInventoryModel, TicketSummaryModel, TicketTimelineModel
from app.infrastructure.db.repositories import SqlAlchemyTicketRepository
from app.infrastructure.db.session import Database


class ReadModelProjection(EventHandler[DomainEvent], ABC):
    """Observer deseni — Observer (ortak taban): bir read model'i olaylardan güncelleyen dinleyici.

    Abonelik kodu (EventSubscriptions) yalnızca bu tabanı bilir: hangi olaylara abone
    olunacağını `source_events` söyler. İki tür vardır: satırı yeniden hesaplayan
    Projector'lar ve satır ekleyen zaman çizelgesi.
    """

    read_model: type[Base]
    source_events: tuple[type[DomainEvent], ...]  # bu read model'i etkileyen olaylar

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    @abstractmethod
    def rebuild(self) -> int:
        """Olay üretmeden yapılan değişikliklerden sonra (seed, elle SQL) read model'i kurar."""


class Projector(ReadModelProjection):
    """Template Method deseni — Abstract Class: refresh/rebuild akışı sabit,
    `all_keys` / `build_row` / `key_of` adımları alt sınıflarda.

    Observer deseni — Concrete Observer: `source_events` olaylarında satırı yeniler.
    """

    key_column: str  # read model'in birincil anahtarı (örn. "ticket_id")

    def handle(self, event: DomainEvent) -> None:
        self.refresh(self.key_of(event))

    def refresh(self, key: int) -> None:
        """Tek bir kaydın satırını kaynaktan yeniden hesaplar (upsert ya da silme)."""
        with self._session_factory() as session:
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
        with self._session_factory() as session:
            session.execute(delete(self.read_model))
            keys = self.all_keys(session)
            for key in keys:
                session.add(self.read_model(**self.build_row(session, key)))
            session.commit()
            return len(keys)

    @abstractmethod
    def key_of(self, event: DomainEvent) -> int:
        """Olaydan, satırı yenilenecek kaydın anahtarını çıkarır."""

    @abstractmethod
    def all_keys(self, session: Session) -> list[int]: ...

    @abstractmethod
    def build_row(self, session: Session, key: int) -> dict[str, Any] | None: ...

    @staticmethod
    def _count_where(session: Session, model: type[Base], **filters: object) -> int:
        statement = select(func.count()).select_from(model).filter_by(**filters)
        return session.scalar(statement)


class TicketSummaryProjector(Projector):
    """Template Method deseni — Concrete Class: read.ticket_summary (talep listeleri)."""

    read_model = TicketSummaryModel
    key_column = "ticket_id"
    source_events = (
        TicketCreated,
        TicketStatusChanged,
        TicketUrgencyChanged,
        AiAnswerRecorded,
        AiFeedbackGiven,
        TicketCommentAdded,
        ScreenshotAttached,
    )

    def key_of(self, event: TicketEvent) -> int:
        return event.ticket_id

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
            "support_level": ticket.support_level.value,
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
            "sla_layers": [asdict(layer) for layer in behavior.layers()],
            "ai_confidence": ai_response.confidence if ai_response else None,
            "ai_feedback": ai_response.user_feedback.value
            if ai_response and ai_response.user_feedback
            else None,
            "comment_count": self._count_where(session, TicketCommentModel, ticket_id=key),
            "attachment_count": self._count_where(session, TicketAttachmentModel, ticket_id=key),
            "created_at": ticket.created_at,
            "resolved_at": ticket.resolved_at,
            "refreshed_at": Clock.now(),
        }


class DeviceInventoryProjector(Projector):
    """Template Method deseni — Concrete Class: read.device_inventory (envanter raporu, zimmetli cihazlarım)."""

    read_model = DeviceInventoryModel
    key_column = "device_id"
    source_events = (
        DeviceRegistered,
        DeviceDetailsUpdated,
        DeviceRetired,
        DeviceAssigned,
        DeviceReturned,
        MaintenanceStarted,
        MaintenanceCompleted,
    )

    def key_of(self, event: DeviceEvent) -> int:
        return event.device_id

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
            "has_open_maintenance": self._count_where(
                session, MaintenanceRecordModel, device_id=key, completed_at=None
            )
            > 0,
            "maintenance_count": self._count_where(session, MaintenanceRecordModel, device_id=key),
            "last_maintenance_at": last_maintenance_at,
            "refreshed_at": Clock.now(),
        }


@dataclass(frozen=True)
class TimelineFact:
    """Bir olayın zaman çizelgesindeki karşılığı: tür, yapan kişi ve türe özgü bilgiler."""

    kind: TimelineEntryKind
    actor_id: int | None
    details: dict[str, Any] = field(default_factory=dict)


class TicketTimelineProjector(ReadModelProjection):
    """Observer deseni — Concrete Observer: talep olaylarını read.ticket_timeline'a satır olarak ekler (E3).

    Her olay türünün kendi açıklayıcı metodu vardır (olay türü → metot sözlüğü; if/elif
    yok). Yeni bir olayı çizelgeye eklemek = bir metot + `source_events`'e bir satır.
    Satırlar yalnızca eklenir: durum geçmişinin tek kaynağı olaylardır.
    """

    read_model = TicketTimelineModel
    source_events = (
        TicketCreated,
        AiAnswerRecorded,
        AiFeedbackGiven,
        TicketStatusChanged,
        TicketCommentAdded,
        ScreenshotAttached,
        TicketUrgencyChanged,
    )
    EXCERPT_LENGTH = 140

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        super().__init__(session_factory)
        self._describers: dict[type[DomainEvent], Callable[[Session, Any], TimelineFact | None]] = {
            TicketCreated: self._created,
            AiAnswerRecorded: self._ai_answered,
            AiFeedbackGiven: self._ai_feedback,
            TicketStatusChanged: self._status_changed,
            TicketCommentAdded: self._comment,
            ScreenshotAttached: self._attachment,
            TicketUrgencyChanged: self._urgency,
        }

    def handle(self, event: TicketEvent) -> None:
        with self._session_factory() as session:
            fact = self._describers[type(event)](session, event)
            if fact is None:
                return
            session.add(self._row(session, event.ticket_id, event.occurred_at, fact))
            session.commit()

    def rebuild(self) -> int:
        """Silmez; hiç kaydı olmayan talepler için bilinenleri (oluşturulma, notlar, ekler)
        write tablolarından doldurur. Doldurulan talep sayısını döner."""
        with self._session_factory() as session:
            covered = select(TicketTimelineModel.ticket_id).distinct()
            tickets = list(session.scalars(select(TicketModel).where(TicketModel.id.not_in(covered))))
            for ticket in tickets:
                session.add(self._row(session, ticket.id, ticket.created_at, TimelineFact(
                    TimelineEntryKind.CREATED, ticket.requester_id)))
                for comment in session.scalars(select(TicketCommentModel).filter_by(ticket_id=ticket.id)):
                    session.add(self._row(session, ticket.id, comment.created_at, self._comment_fact(comment)))
                for attachment in session.scalars(select(TicketAttachmentModel).filter_by(ticket_id=ticket.id)):
                    session.add(self._row(session, ticket.id, attachment.uploaded_at, TimelineFact(
                        TimelineEntryKind.ATTACHMENT, None)))
            session.commit()
            return len(tickets)

    # --- Olay türü → çizelge satırı ---

    def _created(self, session: Session, event: TicketCreated) -> TimelineFact:
        return TimelineFact(TimelineEntryKind.CREATED, event.requester_id, {"sla_hours": event.sla_hours})

    def _ai_answered(self, session: Session, event: AiAnswerRecorded) -> TimelineFact:
        return TimelineFact(
            TimelineEntryKind.AI_ANSWERED, None, {"confidence": event.confidence, "escalated": event.escalated}
        )

    def _ai_feedback(self, session: Session, event: AiFeedbackGiven) -> TimelineFact:
        requester_id = session.scalar(select(TicketModel.requester_id).where(TicketModel.id == event.ticket_id))
        return TimelineFact(TimelineEntryKind.AI_FEEDBACK, requester_id, {"is_helpful": event.is_helpful})

    def _status_changed(self, session: Session, event: TicketStatusChanged) -> TimelineFact | None:
        if event.actor_id is None:
            return None  # AI asistanın geçişi: AI_ANSWERED satırı zaten anlatıyor (tekrar olmasın)
        assignee = session.get(UserModel, event.assignee_id) if event.assignee_id else None
        support_level = session.scalar(select(TicketModel.support_level).where(TicketModel.id == event.ticket_id))
        return TimelineFact(
            TimelineEntryKind.STATUS_CHANGED,
            event.actor_id,
            {
                "old_status": event.old_status.value,
                "new_status": event.new_status.value,
                "assignee_name": assignee.full_name if assignee else None,
                "support_level": support_level.value if support_level else None,
            },
        )

    def _comment(self, session: Session, event: TicketCommentAdded) -> TimelineFact | None:
        comment = session.get(TicketCommentModel, event.comment_id)
        return self._comment_fact(comment) if comment else None

    def _comment_fact(self, comment: TicketCommentModel) -> TimelineFact:
        excerpt = comment.content[: self.EXCERPT_LENGTH]
        if len(comment.content) > self.EXCERPT_LENGTH:
            excerpt += "…"
        return TimelineFact(TimelineEntryKind.COMMENT, comment.author_id, {"excerpt": excerpt})

    def _attachment(self, session: Session, event: ScreenshotAttached) -> TimelineFact:
        return TimelineFact(TimelineEntryKind.ATTACHMENT, event.uploaded_by)

    def _urgency(self, session: Session, event: TicketUrgencyChanged) -> TimelineFact:
        return TimelineFact(
            TimelineEntryKind.URGENCY, event.actor_id, {"is_urgent": event.is_urgent, "sla_hours": event.sla_hours}
        )

    @staticmethod
    def _row(session: Session, ticket_id: int, occurred_at: datetime, fact: TimelineFact) -> TicketTimelineModel:
        actor = session.get(UserModel, fact.actor_id) if fact.actor_id is not None else None
        return TicketTimelineModel(
            ticket_id=ticket_id,
            occurred_at=occurred_at,
            kind=fact.kind.value,
            actor_id=fact.actor_id,
            actor_name=actor.full_name if actor else None,
            details=fact.details,
        )


class ReadModelRebuilder:
    """Tüm read model'leri kurar (seed sonrası, elle SQL sonrası).

    Yeniden hesaplanan read model'ler silinip baştan üretilir; zaman çizelgesi silinmez,
    yalnızca eksik talepler için doldurulur (bkz. TicketTimelineProjector.rebuild).
    """

    PROJECTORS: tuple[type[ReadModelProjection], ...] = (
        TicketSummaryProjector,
        DeviceInventoryProjector,
        TicketTimelineProjector,
    )

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def rebuild_all(self) -> dict[str, int]:
        """Tablo adı → üretilen satır sayısı."""
        return {
            projector_class.read_model.__tablename__: projector_class(self._session_factory).rebuild()
            for projector_class in self.PROJECTORS
        }


def main() -> None:
    # Komut satırı giriş noktası: bağımlılıklar burada kurulur
    from app.core.config import get_settings

    counts = ReadModelRebuilder(Database(get_settings().database_url).session_factory).rebuild_all()
    for table, count in counts.items():
        if table == TicketTimelineProjector.read_model.__tablename__:
            print(f"{table}: {count} talebin eksik geçmişi dolduruldu (mevcut geçmiş korunur).")
        else:
            print(f"{table}: {count} satır yeniden üretildi.")


if __name__ == "__main__":
    main()
