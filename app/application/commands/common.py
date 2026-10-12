"""Command handler'larda tekrar eden kontroller."""

from app.application.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.enums import UserRole
from app.domain.inventory import Device
from app.domain.user import User


def require_role(uow: UnitOfWork, actor_id: int, *allowed_roles: UserRole) -> User:
    """İşlemi yapan kullanıcıyı getirir ve rolünün yetkili olduğunu doğrular."""
    actor = uow.users.get(actor_id)
    if actor is None:
        raise AuthenticationError("İşlemi yapan kullanıcı bulunamadı.")
    if actor.role not in allowed_roles:
        raise PermissionDeniedError("Bu işlem için yetkiniz yok.")
    return actor


def get_device_or_raise(uow: UnitOfWork, device_id: int) -> Device:
    device = uow.devices.get(device_id)
    if device is None:
        raise NotFoundError("Cihaz bulunamadı.")
    return device
