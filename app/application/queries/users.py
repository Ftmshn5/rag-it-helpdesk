"""Kullanıcı sorguları (okuma tarafı)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.application.queries.base import Query, QueryHandler
from app.domain.enums import SupportLevel, UserRole


@dataclass(frozen=True)
class UserView:
    id: int
    full_name: str
    email: str
    role: UserRole
    department: str | None
    is_vip: bool
    support_level: SupportLevel | None  # yalnızca teknisyenlerde dolu


class UserQueries(ABC):
    @abstractmethod
    def get(self, user_id: int) -> UserView | None: ...

    @abstractmethod
    def list_all(self) -> list[UserView]: ...


@dataclass(frozen=True, kw_only=True)
class ListUsersQuery(Query):
    """Kimlik gerektirmez: arayüzdeki kullanıcı seçme kutusu bu listeyle dolar."""


class ListUsersHandler(QueryHandler[ListUsersQuery, list[UserView]]):
    """Kullanıcı listesi (arayüzdeki 'kullanıcı seç' kutusu ve atama ekranı için)."""

    def handle(self, query: ListUsersQuery) -> list[UserView]:
        return self._users.list_all()
