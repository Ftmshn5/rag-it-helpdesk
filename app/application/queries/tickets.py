"""Talep sorguları (CQRS okuma tarafı).

Yazma tarafından farkları:
- Domain nesnesi (Ticket) kurulmaz, repository / Unit of Work kullanılmaz.
- Ekranın ihtiyacına göre şekillendirilmiş düz veri (DTO / "view") döner.
- İş kuralı yoktur; yalnızca "kim neyi görebilir" kontrolü yapılır.

Listeler denormalize read model'den (read.ticket_summary), talep detayı ise
read model + write tablolarından (açıklama, notlar, ekler, AI yanıtı) gelir.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime

from app.application.errors import NotFoundError, PermissionDeniedError
from app.application.interfaces.file_storage import FileStorage
from app.application.queries.base import ActorQuery, QueryHandler, TQuery, TResult
from app.application.queries.users import UserQueries
from app.domain.enums import AiFeedback, TicketCategory, TicketStatus, UserRole

# --- DTO'lar ---


@dataclass(frozen=True)
class TicketSummaryView:
    ticket_id: int
    title: str
    category: TicketCategory
    status: TicketStatus
    requester_id: int
    requester_name: str
    assignee_id: int | None
    assignee_name: str | None
    device_asset_tag: str | None
    is_vip: bool
    is_urgent: bool
    sla_hours: int
    priority_score: int
    due_at: datetime
    is_overdue: bool
    ai_confidence: float | None
    ai_feedback: AiFeedback | None
    comment_count: int
    attachment_count: int
    created_at: datetime
    resolved_at: datetime | None


@dataclass(frozen=True)
class AiAnswerView:
    answer: str
    confidence: float
    sources: list[str]
    user_feedback: AiFeedback | None


@dataclass(frozen=True)
class CommentView:
    id: int
    author_id: int
    author_name: str
    content: str
    created_at: datetime


@dataclass(frozen=True)
class AttachmentView:
    id: int
    mime_type: str
    uploaded_at: datetime


@dataclass(frozen=True)
class TicketDetailView:
    summary: TicketSummaryView
    description: str
    ai_answer: AiAnswerView | None
    comments: list[CommentView] = field(default_factory=list)
    attachments: list[AttachmentView] = field(default_factory=list)


# --- Okuma arayüzü ---


class TicketQueries(ABC):
    @abstractmethod
    def list_by_requester(
        self, requester_id: int, status: TicketStatus | None = None
    ) -> list[TicketSummaryView]:
        """En yeni talep önce."""

    @abstractmethod
    def list_by_assignee(
        self, assignee_id: int, status: TicketStatus | None = None
    ) -> list[TicketSummaryView]:
        """İş kuyruğu sırası: öncelik puanı yüksek olan, sonra son tarihi yakın olan önce."""

    @abstractmethod
    def list_all(self, status: TicketStatus | None = None) -> list[TicketSummaryView]:
        """İş kuyruğu sırasıyla tüm talepler (yönetici)."""

    @abstractmethod
    def get_detail(self, ticket_id: int) -> TicketDetailView | None: ...

    @abstractmethod
    def get_attachment(self, ticket_id: int, attachment_id: int) -> "AttachmentFileView | None":
        """Ekin depolama yolu ve talebin tarafları; ek bu talebe ait değilse None."""


@dataclass(frozen=True)
class AttachmentFileView:
    file_path: str
    mime_type: str
    requester_id: int
    assignee_id: int | None


@dataclass(frozen=True)
class AttachmentContentView:
    """Ekran görüntüsünün kendisi ve türü (API bunu dosya yanıtı olarak döner)."""

    content: bytes
    mime_type: str


# --- Sorgular ---


@dataclass(frozen=True, kw_only=True)
class ListMyTicketsQuery(ActorQuery):
    status: TicketStatus | None = None


@dataclass(frozen=True, kw_only=True)
class ListAssignedTicketsQuery(ActorQuery):
    status: TicketStatus | None = None


@dataclass(frozen=True, kw_only=True)
class ListAllTicketsQuery(ActorQuery):
    status: TicketStatus | None = None


@dataclass(frozen=True, kw_only=True)
class GetTicketDetailQuery(ActorQuery):
    ticket_id: int


@dataclass(frozen=True, kw_only=True)
class GetAttachmentFileQuery(ActorQuery):
    ticket_id: int
    attachment_id: int


# --- Sorgu handler'ları ---


class TicketQueryHandler(QueryHandler[TQuery, TResult]):
    """Talep sorgularının ortak tabanı: talep okuma arayüzünü de alır."""

    def __init__(self, tickets: TicketQueries, users: UserQueries) -> None:
        super().__init__(users)
        self._tickets = tickets


class ListMyTicketsHandler(TicketQueryHandler[ListMyTicketsQuery, list[TicketSummaryView]]):
    """UC-03: kullanıcı kendi taleplerini listeler."""

    def handle(self, query: ListMyTicketsQuery) -> list[TicketSummaryView]:
        actor = self._require_viewer(query.actor_id)
        return self._tickets.list_by_requester(actor.id, query.status)


class ListAssignedTicketsHandler(TicketQueryHandler[ListAssignedTicketsQuery, list[TicketSummaryView]]):
    """UC-05: teknisyen kendisine atanan talepleri öncelik sırasıyla listeler."""

    def handle(self, query: ListAssignedTicketsQuery) -> list[TicketSummaryView]:
        actor = self._require_viewer(query.actor_id, UserRole.TECHNICIAN)
        return self._tickets.list_by_assignee(actor.id, query.status)


class ListAllTicketsHandler(TicketQueryHandler[ListAllTicketsQuery, list[TicketSummaryView]]):
    """Yönetici kuyruğu: örn. status=ESCALATED ile atama bekleyen talepler (UC-10 öncesi)."""

    def handle(self, query: ListAllTicketsQuery) -> list[TicketSummaryView]:
        self._require_viewer(query.actor_id, UserRole.ADMIN)
        return self._tickets.list_all(query.status)


class GetTicketDetailHandler(TicketQueryHandler[GetTicketDetailQuery, TicketDetailView]):
    def __init__(self, tickets: TicketQueries, users: UserQueries, ai_threshold: float) -> None:
        super().__init__(tickets, users)
        self._ai_threshold = ai_threshold

    def handle(self, query: GetTicketDetailQuery) -> TicketDetailView:
        actor = self._require_viewer(query.actor_id)
        detail = self._tickets.get_detail(query.ticket_id)
        if detail is None:
            raise NotFoundError("Talep bulunamadı.")

        summary = detail.summary
        is_staff = actor.id == summary.assignee_id or actor.role == UserRole.ADMIN
        if actor.id != summary.requester_id and not is_staff:
            raise PermissionDeniedError("Bu talebi görüntüleme yetkiniz yok.")

        # İş kuralı 4'ün okuma tarafı: güveni düşük AI yanıtı talep sahibine
        # gösterilmez; teknisyen ve yönetici bağlam olarak görebilir.
        answer = detail.ai_answer
        if answer and answer.confidence < self._ai_threshold and not is_staff:
            detail = replace(detail, ai_answer=None)
        return detail


class GetAttachmentFileHandler(TicketQueryHandler[GetAttachmentFileQuery, AttachmentContentView]):
    """Ekran görüntüsünün kendisi (UC-15'in görüntüleme tarafı).

    Ek yükleme kuralıyla aynı: yalnızca talebin tarafları (talep sahibi,
    atanan teknisyen, yönetici) görebilir.
    """

    def __init__(self, tickets: TicketQueries, users: UserQueries, storage: FileStorage) -> None:
        super().__init__(tickets, users)
        self._storage = storage

    def handle(self, query: GetAttachmentFileQuery) -> AttachmentContentView:
        actor = self._require_viewer(query.actor_id)
        attachment = self._tickets.get_attachment(query.ticket_id, query.attachment_id)
        if attachment is None:
            raise NotFoundError("Ek bulunamadı.")
        is_participant = actor.id in (attachment.requester_id, attachment.assignee_id)
        if not is_participant and actor.role != UserRole.ADMIN:
            raise PermissionDeniedError("Bu eki görüntüleme yetkiniz yok.")
        try:
            content = self._storage.read(attachment.file_path)
        except FileNotFoundError:
            raise NotFoundError("Ek dosyası depolamada bulunamadı.") from None
        return AttachmentContentView(content=content, mime_type=attachment.mime_type)
