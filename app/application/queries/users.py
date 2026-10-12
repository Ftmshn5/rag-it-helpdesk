"""Kullanıcı sorguları (okuma tarafı)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.application.errors import AuthenticationError, PermissionDeniedError
from app.domain.enums import UserRole


@dataclass(frozen=True)
class UserView:
    id: int
    full_name: str
    email: str
    role: UserRole
    department: str | None
    is_vip: bool


class UserQueries(ABC):
    @abstractmethod
    def get(self, user_id: int) -> UserView | None: ...

    @abstractmethod
    def list_all(self) -> list[UserView]: ...


def require_viewer(users: UserQueries, actor_id: int, *allowed_roles: UserRole) -> UserView:
    """Sorguyu yapan kullanıcıyı getirir; rol verildiyse yetkisini doğrular."""
    actor = users.get(actor_id)
    if actor is None:
        raise AuthenticationError("İşlemi yapan kullanıcı bulunamadı.")
    if allowed_roles and actor.role not in allowed_roles:
        raise PermissionDeniedError("Bu bilgiyi görüntüleme yetkiniz yok.")
    return actor


class ListUsersHandler:
    """Kullanıcı listesi (arayüzdeki 'kullanıcı seç' kutusu ve atama ekranı için)."""

    def __init__(self, users: UserQueries) -> None:
        self.users = users

    def handle(self) -> list[UserView]:
        return self.users.list_all()
