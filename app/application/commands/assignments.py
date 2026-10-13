"""Zimmet command'ları (UC-09: cihaz zimmetle / iade al).

İki kaydı birlikte değiştirirler (Assignment + Device.status); Unit of Work
sayesinde ikisi tek transaction'da kaydedilir ya da hiçbiri kaydedilmez.
"""

from dataclasses import dataclass

from app.application.commands.common import get_device_or_raise, require_role
from app.application.errors import NotFoundError
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.enums import UserRole
from app.domain.errors import DeviceAlreadyAssignedError, DeviceNotAssignedError
from app.domain.events import DeviceAssigned, DeviceReturned
from app.domain.inventory import Assignment


@dataclass(frozen=True, kw_only=True)
class AssignDevice:
    actor_id: int
    device_id: int
    user_id: int


class AssignDeviceHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: AssignDevice) -> int:
        """Cihazı kullanıcıya zimmetler ve zimmet kaydının id'sini döndürür."""
        with self.uow:
            admin = require_role(self.uow, command.actor_id, UserRole.ADMIN)
            device = get_device_or_raise(self.uow, command.device_id)
            if self.uow.users.get(command.user_id) is None:
                raise NotFoundError("Zimmetlenecek kullanıcı bulunamadı.")

            # İş kuralı 1: bir cihazın aynı anda tek aktif zimmeti olabilir.
            # Asıl kontrol domain'de: yalnızca depodaki cihaz zimmetlenir (duruma
            # özgü, anlaşılır hata mesajıyla). Ardından gelen sorgu, durum ile
            # zimmet kayıtları bir şekilde çelişirse devreye giren ikinci güvencedir.
            device.assign()
            if self.uow.assignments.get_active_for_device(device.id):
                raise DeviceAlreadyAssignedError("Cihazın zaten aktif bir zimmeti var.")

            assignment = self.uow.assignments.add(
                Assignment(device_id=device.id, user_id=command.user_id, assigned_by=admin.id)
            )
            self.uow.devices.update(device)
            self.uow.add_event(
                DeviceAssigned(
                    device_id=device.id, user_id=command.user_id, assignment_id=assignment.id
                )
            )
            self.uow.commit()
            return assignment.id


@dataclass(frozen=True, kw_only=True)
class ReturnDevice:
    actor_id: int
    device_id: int


class ReturnDeviceHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: ReturnDevice) -> None:
        with self.uow:
            require_role(self.uow, command.actor_id, UserRole.ADMIN)
            device = get_device_or_raise(self.uow, command.device_id)

            assignment = self.uow.assignments.get_active_for_device(device.id)
            if assignment is None:
                raise DeviceNotAssignedError("Cihazın aktif bir zimmeti yok.")

            device.mark_returned()
            assignment.close()

            self.uow.assignments.update(assignment)
            self.uow.devices.update(device)
            self.uow.add_event(
                DeviceReturned(
                    device_id=device.id, user_id=assignment.user_id, assignment_id=assignment.id
                )
            )
            self.uow.commit()
