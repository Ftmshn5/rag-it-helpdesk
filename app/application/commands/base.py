"""CQRS yazma tarafının ortak tabanları.

Her command iki sınıftan oluşur:
- Command (veri): "Ne yapılmak isteniyor?" — değiştirilemez dataclass.
- CommandHandler (davranış): "Nasıl yapılır?" — tek bir command'ı yürütür.

Handler'ların hepsi CommandHandler'dan türer (kalıtım): Unit of Work'ü
constructor'dan alır (Dependency Injection) ve tekrar eden kontrolleri (yetki,
"kayıt bulunamadı") korumalı metotlar olarak buradan devralır. Alt sınıflar
yalnızca kendi iş akışlarını (handle) yazar.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from app.application.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.enums import UserRole
from app.domain.inventory import Device
from app.domain.ticket import Ticket
from app.domain.user import User


@dataclass(frozen=True, kw_only=True)
class Command:
    """Tüm command'ların tabanı: bir yazma isteğinin değiştirilemez verisi."""


@dataclass(frozen=True, kw_only=True)
class ActorCommand(Command):
    """Bir kullanıcının başlattığı command; actor_id ile kim olduğu ve yetkisi belirlenir."""

    actor_id: int


TCommand = TypeVar("TCommand", bound=Command)
TResult = TypeVar("TResult")


class CommandHandler(ABC, Generic[TCommand, TResult]):
    """Tüm command handler'ların soyut tabanı.

    Somut handler'lar `handle` metodunu uygular; değişikliklerini Unit of Work
    içinde yapar (`with self._uow: ... self._uow.commit()`).
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    @abstractmethod
    def handle(self, command: TCommand) -> TResult:
        """Command'ı yürütür. Oluşturma işlemleri yeni kaydın id'sini, diğerleri None döner."""

    # --- Ortak kontroller (alt sınıflar devralır) ---

    def _require_actor(self, actor_id: int, *allowed_roles: UserRole) -> User:
        """İşlemi yapan kullanıcıyı getirir; rol verildiyse yetkisini doğrular (boşsa her rol)."""
        actor = self._uow.users.get(actor_id)
        if actor is None:
            raise AuthenticationError("İşlemi yapan kullanıcı bulunamadı.")
        if allowed_roles and actor.role not in allowed_roles:
            raise PermissionDeniedError("Bu işlem için yetkiniz yok.")
        return actor

    def _get_user(self, user_id: int, not_found_message: str) -> User:
        user = self._uow.users.get(user_id)
        if user is None:
            raise NotFoundError(not_found_message)
        return user

    def _get_device(self, device_id: int) -> Device:
        device = self._uow.devices.get(device_id)
        if device is None:
            raise NotFoundError("Cihaz bulunamadı.")
        return device

    def _get_ticket(self, ticket_id: int) -> Ticket:
        ticket = self._uow.tickets.get(ticket_id)
        if ticket is None:
            raise NotFoundError("Talep bulunamadı.")
        return ticket
