"""Okuma arayüzlerinin SQL implementasyonları.

Listeler yalnızca read.ticket_summary tablosunu okur (JOIN yok). Talep detayı,
özet satırına ek olarak tek tablodan gelen bilgileri (açıklama, notlar, ekler,
AI yanıtı) doğrudan write tablolarından salt okunur sorgularla alır.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.queries.tickets import (
    AiAnswerView,
    AttachmentView,
    CommentView,
    TicketDetailView,
    TicketQueries,
    TicketSummaryView,
)
from app.application.queries.users import UserQueries, UserView
from app.domain.clock import utc_now
from app.domain.enums import AiFeedback, TicketCategory, TicketStatus
from app.infrastructure.db.models import (
    AIResponseModel,
    TicketAttachmentModel,
    TicketCommentModel,
    TicketModel,
    UserModel,
)
from app.infrastructure.db.read_models import TicketSummaryModel

FINISHED = {TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value}

# İş kuyruğu sırası: Decorator'ın hesapladığı öncelik puanı burada işe yarar
WORK_QUEUE_ORDER = (
    TicketSummaryModel.priority_score.desc(),
    TicketSummaryModel.due_at.asc(),
)


def to_summary_view(row: TicketSummaryModel) -> TicketSummaryView:
    return TicketSummaryView(
        ticket_id=row.ticket_id,
        title=row.title,
        category=TicketCategory(row.category),
        status=TicketStatus(row.status),
        requester_id=row.requester_id,
        requester_name=row.requester_name,
        assignee_id=row.assignee_id,
        assignee_name=row.assignee_name,
        device_asset_tag=row.device_asset_tag,
        is_vip=row.is_vip,
        is_urgent=row.is_urgent,
        sla_hours=row.sla_hours,
        priority_score=row.priority_score,
        due_at=row.due_at,
        # Zamana bağlı olduğu için saklanmaz, okurken hesaplanır
        is_overdue=row.status not in FINISHED and row.due_at < utc_now(),
        ai_confidence=row.ai_confidence,
        ai_feedback=AiFeedback(row.ai_feedback) if row.ai_feedback else None,
        comment_count=row.comment_count,
        attachment_count=row.attachment_count,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
    )


class SqlTicketQueries(TicketQueries):
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_by_requester(self, requester_id, status=None):
        statement = (
            select(TicketSummaryModel)
            .where(TicketSummaryModel.requester_id == requester_id)
            .order_by(TicketSummaryModel.created_at.desc())
        )
        return self._list(statement, status)

    def list_by_assignee(self, assignee_id, status=None):
        statement = (
            select(TicketSummaryModel)
            .where(TicketSummaryModel.assignee_id == assignee_id)
            .order_by(*WORK_QUEUE_ORDER)
        )
        return self._list(statement, status)

    def list_all(self, status=None):
        return self._list(select(TicketSummaryModel).order_by(*WORK_QUEUE_ORDER), status)

    def _list(self, statement, status: TicketStatus | None) -> list[TicketSummaryView]:
        if status is not None:
            statement = statement.where(TicketSummaryModel.status == status.value)
        return [to_summary_view(row) for row in self.session.scalars(statement)]

    def get_detail(self, ticket_id: int) -> TicketDetailView | None:
        summary = self.session.get(TicketSummaryModel, ticket_id)
        if summary is None:
            return None
        description = self.session.scalar(
            select(TicketModel.description).where(TicketModel.id == ticket_id)
        )
        ai = self.session.scalar(select(AIResponseModel).where(AIResponseModel.ticket_id == ticket_id))
        comments = self.session.execute(
            select(TicketCommentModel, UserModel.full_name)
            .join(UserModel, UserModel.id == TicketCommentModel.author_id)
            .where(TicketCommentModel.ticket_id == ticket_id)
            .order_by(TicketCommentModel.created_at)
        )
        attachments = self.session.scalars(
            select(TicketAttachmentModel)
            .where(TicketAttachmentModel.ticket_id == ticket_id)
            .order_by(TicketAttachmentModel.uploaded_at)
        )
        return TicketDetailView(
            summary=to_summary_view(summary),
            description=description,
            ai_answer=AiAnswerView(
                answer=ai.answer,
                confidence=ai.confidence,
                sources=list(ai.sources),
                user_feedback=ai.user_feedback,
            )
            if ai
            else None,
            comments=[
                CommentView(
                    id=comment.id,
                    author_id=comment.author_id,
                    author_name=author_name,
                    content=comment.content,
                    created_at=comment.created_at,
                )
                for comment, author_name in comments
            ],
            attachments=[
                AttachmentView(id=a.id, mime_type=a.mime_type, uploaded_at=a.uploaded_at)
                for a in attachments
            ],
        )


class SqlUserQueries(UserQueries):
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: int) -> UserView | None:
        user = self.session.get(UserModel, user_id)
        return self._to_view(user) if user else None

    def list_all(self) -> list[UserView]:
        users = self.session.scalars(select(UserModel).order_by(UserModel.role, UserModel.full_name))
        return [self._to_view(user) for user in users]

    @staticmethod
    def _to_view(user: UserModel) -> UserView:
        return UserView(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=user.role,
            department=user.department,
            is_vip=user.is_vip,
        )
