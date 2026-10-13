"""CQRS okuma tarafının ortak tabanları.

Yazma tarafıyla aynı yapı: her sorgu bir Query (veri) ve bir QueryHandler
(davranış) sınıfıdır. Fark: query handler'lar domain nesnesi, repository veya
Unit of Work kullanmaz; okuma arayüzlerinden (UserQueries, TicketQueries …)
ekrana göre şekillenmiş düz veri (view / DTO) döner.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from app.application.errors import AuthenticationError, PermissionDeniedError
from app.domain.enums import UserRole

if TYPE_CHECKING:  # döngüsel import olmasın diye yalnızca tip denetiminde
    from app.application.queries.users import UserQueries, UserView


@dataclass(frozen=True, kw_only=True)
class Query:
    """Tüm sorguların tabanı: bir okuma isteğinin değiştirilemez verisi."""


@dataclass(frozen=True, kw_only=True)
class ActorQuery(Query):
    """Bir kullanıcının yaptığı sorgu; kim olduğu ve neyi görebileceği actor_id ile belirlenir."""

    actor_id: int


TQuery = TypeVar("TQuery", bound=Query)
TResult = TypeVar("TResult")


class QueryHandler(ABC, Generic[TQuery, TResult]):
    """Tüm query handler'ların soyut tabanı.

    Her handler "kim neyi görebilir" kontrolü için kullanıcı okuma arayüzüne
    ihtiyaç duyar; bu yüzden UserQueries tabanda enjekte edilir.
    """

    def __init__(self, users: UserQueries) -> None:
        self._users = users

    @abstractmethod
    def handle(self, query: TQuery) -> TResult:
        """Sorguyu yürütür ve view nesne(ler)i döndürür."""

    def _require_viewer(self, actor_id: int, *allowed_roles: UserRole) -> UserView:
        """Sorguyu yapan kullanıcıyı getirir; rol verildiyse yetkisini doğrular (boşsa her rol)."""
        actor = self._users.get(actor_id)
        if actor is None:
            raise AuthenticationError("İşlemi yapan kullanıcı bulunamadı.")
        if allowed_roles and actor.role not in allowed_roles:
            raise PermissionDeniedError("Bu bilgiyi görüntüleme yetkiniz yok.")
        return actor
