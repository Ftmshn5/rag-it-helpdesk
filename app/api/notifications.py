"""Bildirim endpoint'leri: kullanıcının zil menüsü."""

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.application.commands.notifications import MarkNotificationsReadCommand, MarkNotificationsReadHandler
from app.application.queries.notifications import (
    GetMyNotificationsHandler,
    GetMyNotificationsQuery,
    MyNotificationsView,
)
from app.core.dependencies import (
    get_current_user_id,
    get_mark_notifications_read_handler,
    get_my_notifications_handler,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


class MarkNotificationsReadRequest(BaseModel):
    notification_ids: list[int] = Field(default_factory=list, description="Boş: tüm okunmamış bildirimler")


@router.get("/mine", response_model=MyNotificationsView)
def get_my_notifications(
    limit: int = Query(default=20, ge=1, le=50),
    actor_id: int = Depends(get_current_user_id),
    handler: GetMyNotificationsHandler = Depends(get_my_notifications_handler),
) -> MyNotificationsView:
    return handler.handle(GetMyNotificationsQuery(actor_id=actor_id, limit=limit))


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notifications_read(
    body: MarkNotificationsReadRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: MarkNotificationsReadHandler = Depends(get_mark_notifications_read_handler),
) -> None:
    handler.handle(MarkNotificationsReadCommand(actor_id=actor_id, notification_ids=tuple(body.notification_ids)))
