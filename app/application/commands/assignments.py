"""Zimmet command'ları (UC-09: cihaz zimmetle / iade al).

İki kaydı birlikte değiştirirler (Assignment + Device.status); Unit of Work
sayesinde ikisi tek transaction'da kaydedilir ya da hiçbiri kaydedilmez.
"""

from dataclasses import dataclass

from app.application.commands.base import ActorCommand, CommandHandler
from app.domain.enums import UserRole
from app.domain.errors import DeviceAlreadyAssignedError, DeviceNotAssignedError
from app.domain.events import DeviceAssigned, DeviceReturned
from app.domain.inventory import Assignment


@dataclass(frozen=True, kw_only=True)
class AssignDeviceCommand(ActorCommand):
    device_id: int
    user_id: int


class AssignDeviceHandler(CommandHandler[AssignDeviceCommand, int]):
    def handle(self, command: AssignDeviceCommand) -> int:
        """Cihazı kullanıcıya zimmetler ve zimmet kaydının id'sini döndürür."""
        with self._uow:
            admin = self._require_actor(command.actor_id, UserRole.ADMIN)
            device = self._get_device(command.device_id)
            self._get_user(command.user_id, "Zimmetlenecek kullanıcı bulunamadı.")

            # İş kuralı 1: bir cihazın aynı anda tek aktif zimmeti olabilir.
            # Asıl kontrol domain'de: yalnızca depodaki cihaz zimmetlenir (duruma
            # özgü, anlaşılır hata mesajıyla). Ardından gelen sorgu, durum ile
            # zimmet kayıtları bir şekilde çelişirse devreye giren ikinci güvencedir.
            device.assign()
            if self._uow.assignments.get_active_for_device(device.id):
                raise DeviceAlreadyAssignedError("Cihazın zaten aktif bir zimmeti var.")

            assignment = self._uow.assignments.add(
                Assignment(device_id=device.id, user_id=command.user_id, assigned_by=admin.id)
            )
            self._uow.devices.update(device)
            self._uow.add_event(
                DeviceAssigned(device_id=device.id, user_id=command.user_id, assignment_id=assignment.id)
            )
            self._uow.commit()
            return assignment.id


@dataclass(frozen=True, kw_only=True)
class ReturnDeviceCommand(ActorCommand):
    device_id: int


class ReturnDeviceHandler(CommandHandler[ReturnDeviceCommand, None]):
    def handle(self, command: ReturnDeviceCommand) -> None:
        with self._uow:
            self._require_actor(command.actor_id, UserRole.ADMIN)
            device = self._get_device(command.device_id)

            assignment = self._uow.assignments.get_active_for_device(device.id)
            if assignment is None:
                raise DeviceNotAssignedError("Cihazın aktif bir zimmeti yok.")

            device.mark_returned()
            assignment.close()

            self._uow.assignments.update(assignment)
            self._uow.devices.update(device)
            self._uow.add_event(
                DeviceReturned(device_id=device.id, user_id=assignment.user_id, assignment_id=assignment.id)
            )
            self._uow.commit()
