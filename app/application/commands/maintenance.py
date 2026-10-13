"""Bakım command'ları (UC-16: cihaza bakım/onarım kaydı gir).

İş kuralı 2: bakım kaydı açılınca cihaz IN_REPAIR olur, kapanınca önceki
durumuna döner. Kuralın kendisi domain'de (MaintenanceRecord.open/complete);
handler'lar yetki, kayıt yükleme ve transaction'ı yönetir.
"""

from dataclasses import dataclass

from app.application.commands.base import ActorCommand, CommandHandler
from app.application.errors import NotFoundError
from app.domain.enums import MaintenanceType, UserRole
from app.domain.errors import MaintenanceAlreadyOpenError
from app.domain.events import MaintenanceCompleted, MaintenanceStarted
from app.domain.inventory import MaintenanceRecord


@dataclass(frozen=True, kw_only=True)
class StartMaintenanceCommand(ActorCommand):
    device_id: int
    type: MaintenanceType
    description: str
    ticket_id: int | None = None


class StartMaintenanceHandler(CommandHandler[StartMaintenanceCommand, int]):
    def handle(self, command: StartMaintenanceCommand) -> int:
        """Bakım kaydını açar ve id'sini döndürür."""
        with self._uow:
            technician = self._require_actor(command.actor_id, UserRole.TECHNICIAN)
            device = self._get_device(command.device_id)
            if command.ticket_id is not None and self._uow.tickets.get(command.ticket_id) is None:
                raise NotFoundError("İlişkilendirilecek talep bulunamadı.")

            record = MaintenanceRecord.open(
                device=device,
                technician_id=technician.id,
                type=command.type,
                description=command.description,
                ticket_id=command.ticket_id,
            )
            # İkinci güvence (DB'de de koşullu benzersiz indeks var): tek açık bakım
            if self._uow.maintenance_records.get_open_for_device(device.id):
                raise MaintenanceAlreadyOpenError()

            record = self._uow.maintenance_records.add(record)
            self._uow.devices.update(device)
            self._uow.add_event(
                MaintenanceStarted(
                    maintenance_record_id=record.id, device_id=device.id, technician_id=technician.id
                )
            )
            self._uow.commit()
            return record.id


@dataclass(frozen=True, kw_only=True)
class CompleteMaintenanceCommand(ActorCommand):
    maintenance_record_id: int


class CompleteMaintenanceHandler(CommandHandler[CompleteMaintenanceCommand, None]):
    def handle(self, command: CompleteMaintenanceCommand) -> None:
        with self._uow:
            self._require_actor(command.actor_id, UserRole.TECHNICIAN)
            record = self._uow.maintenance_records.get(command.maintenance_record_id)
            if record is None:
                raise NotFoundError("Bakım kaydı bulunamadı.")
            device = self._get_device(record.device_id)

            record.complete(device)

            self._uow.maintenance_records.update(record)
            self._uow.devices.update(device)
            self._uow.add_event(MaintenanceCompleted(maintenance_record_id=record.id, device_id=device.id))
            self._uow.commit()
