"""Okuma arayüzlerinin SQL implementasyonları.

Listeler yalnızca read şemasındaki tabloları okur (JOIN yok). Talep detayı,
özet satırına ek olarak tek tablodan gelen bilgileri (açıklama, notlar, ekler,
AI yanıtı) doğrudan write tablolarından salt okunur sorgularla alır.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.queries.inventory import (
    DeviceInventoryView,
    InventoryQueries,
    MaintenanceRecordView,
)
from app.application.queries.tickets import (
    AiAnswerView,
    AttachmentFileView,
    AttachmentView,
    CommentView,
    TicketDetailView,
    TicketQueries,
    TicketSummaryView,
)
from app.application.queries.users import UserQueries, UserView
from app.domain.clock import utc_now
from app.domain.enums import AiFeedback, DeviceStatus, TicketCategory, TicketStatus
from app.infrastructure.db.models import (
    AIResponseModel,
    DeviceModel,
    MaintenanceRecordModel,
    TicketAttachmentModel,
    TicketCommentModel,
    TicketModel,
    UserModel,
)
from app.infrastructure.db.read_models import DeviceInventoryModel, TicketSummaryModel

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

    def get_attachment(self, ticket_id: int, attachment_id: int) -> AttachmentFileView | None:
        row = self.session.execute(
            select(
                TicketAttachmentModel.file_path,
                TicketAttachmentModel.mime_type,
                TicketModel.requester_id,
                TicketModel.assignee_id,
            )
            .join(TicketModel, TicketModel.id == TicketAttachmentModel.ticket_id)
            .where(
                TicketAttachmentModel.id == attachment_id,
                # Ek gerçekten bu talebe mi ait? Başka talebin eki bu adresle açılamaz.
                TicketAttachmentModel.ticket_id == ticket_id,
            )
        ).first()
        return AttachmentFileView(*row) if row else None


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


def to_inventory_view(row: DeviceInventoryModel) -> DeviceInventoryView:
    return DeviceInventoryView(
        device_id=row.device_id,
        asset_tag=row.asset_tag,
        type=row.type,
        brand=row.brand,
        model=row.model,
        serial_number=row.serial_number,
        status=DeviceStatus(row.status),
        location=row.location,
        purchase_date=row.purchase_date,
        holder_id=row.holder_id,
        holder_name=row.holder_name,
        holder_department=row.holder_department,
        assigned_at=row.assigned_at,
        has_open_maintenance=row.has_open_maintenance,
        maintenance_count=row.maintenance_count,
        last_maintenance_at=row.last_maintenance_at,
    )


class SqlInventoryQueries(InventoryQueries):
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_devices(self, status=None, device_type=None):
        statement = select(DeviceInventoryModel).order_by(DeviceInventoryModel.asset_tag)
        if status is not None:
            statement = statement.where(DeviceInventoryModel.status == status.value)
        if device_type is not None:
            statement = statement.where(DeviceInventoryModel.type == device_type)
        return [to_inventory_view(row) for row in self.session.scalars(statement)]

    def list_held_by(self, user_id):
        statement = (
            select(DeviceInventoryModel)
            .where(DeviceInventoryModel.holder_id == user_id)
            .order_by(DeviceInventoryModel.asset_tag)
        )
        return [to_inventory_view(row) for row in self.session.scalars(statement)]

    def device_exists(self, device_id):
        return self.session.get(DeviceModel, device_id) is not None

    def maintenance_history(self, device_id):
        rows = self.session.execute(
            select(MaintenanceRecordModel, UserModel.full_name)
            .join(UserModel, UserModel.id == MaintenanceRecordModel.technician_id)
            .where(MaintenanceRecordModel.device_id == device_id)
            .order_by(MaintenanceRecordModel.performed_at.desc())
        )
        return [
            MaintenanceRecordView(
                id=record.id,
                type=record.type,
                description=record.description,
                technician_id=record.technician_id,
                technician_name=technician_name,
                ticket_id=record.ticket_id,
                performed_at=record.performed_at,
                completed_at=record.completed_at,
                is_open=record.completed_at is None,
            )
            for record, technician_name in rows
        ]
