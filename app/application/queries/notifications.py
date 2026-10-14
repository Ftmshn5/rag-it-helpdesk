"""Bildirim sorguları (okuma tarafı): kullanıcının zil menüsü.

Tek tablodan geldiği için read model yerine write tablosundan salt okunur
sorguyla okunur (talep notları gibi).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.application.queries.base import ActorQuery, QueryHandler
from app.application.queries.users import UserQueries
from app.domain.notifications import NotificationChannel


@dataclass(frozen=True)
class NotificationView:
    id: int
    ticket_id: int | None
    channel: NotificationChannel
    message: str
    created_at: datetime
    is_read: bool


@dataclass(frozen=True)
class MyNotificationsView:
    unread_count: int
    items: list[NotificationView]  # en yeniler önce


class NotificationQueries(ABC):
    @abstractmethod
    def recent_for(self, user_id: int, limit: int) -> list[NotificationView]: ...

    @abstractmethod
    def unread_count(self, user_id: int) -> int: ...


@dataclass(frozen=True, kw_only=True)
class GetMyNotificationsQuery(ActorQuery):
    limit: int = 20


class GetMyNotificationsHandler(QueryHandler[GetMyNotificationsQuery, MyNotificationsView]):
    """Her kullanıcı yalnızca kendi bildirimlerini görür (her rol)."""

    MAX_LIMIT = 50

    def __init__(self, notifications: NotificationQueries, users: UserQueries) -> None:
        super().__init__(users)
        self._notifications = notifications

    def handle(self, query: GetMyNotificationsQuery) -> MyNotificationsView:
        viewer = self._require_viewer(query.actor_id)
        limit = min(max(query.limit, 1), self.MAX_LIMIT)
        return MyNotificationsView(
            unread_count=self._notifications.unread_count(viewer.id),
            items=self._notifications.recent_for(viewer.id, limit),
        )
