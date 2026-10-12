"""Bakım command'ları (UC-16: cihaza bakım/onarım kaydı gir).

İş kuralı 2: bakım kaydı açılınca cihaz IN_REPAIR olur, kapanınca önceki
durumuna döner. Kuralın kendisi domain'de (MaintenanceRecord.open/complete);
handler'lar yetki, kayıt yükleme ve transaction'ı yönetir.
"""

from dataclasses import dataclass

from app.application.commands.common import get_device_or_raise, require_role
from app.application.errors import NotFoundError
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.enums import MaintenanceType, UserRole
from app.domain.errors import BusinessRuleViolation
from app.domain.events import MaintenanceCompleted, MaintenanceStarted
from app.domain.inventory import MaintenanceRecord


@dataclass(frozen=True, kw_only=True)
class StartMaintenance:
    actor_id: int
    device_id: int
    type: MaintenanceType
    description: str
    ticket_id: int | None = None


class StartMaintenanceHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: StartMaintenance) -> int:
        """Bakım kaydını açar ve id'sini döndürür."""
        with self.uow:
            technician = require_role(self.uow, command.actor_id, UserRole.TECHNICIAN)
            device = get_device_or_raise(self.uow, command.device_id)
            if command.ticket_id is not None and self.uow.tickets.get(command.ticket_id) is None:
                raise NotFoundError("İlişkilendirilecek talep bulunamadı.")

            record = MaintenanceRecord.open(
                device=device,
                technician_id=technician.id,
                type=command.type,
                description=command.description,
                ticket_id=command.ticket_id,
            )
            # İkinci güvence (DB'de de koşullu benzersiz indeks var): tek açık bakım
            if self.uow.maintenance_records.get_open_for_device(device.id):
                raise BusinessRuleViolation("Cihazın zaten açık bir bakım kaydı var.")

            record = self.uow.maintenance_records.add(record)
            self.uow.devices.update(device)
            self.uow.add_event(
                MaintenanceStarted(
                    maintenance_record_id=record.id,
                    device_id=device.id,
                    technician_id=technician.id,
                )
            )
            self.uow.commit()
            return record.id


@dataclass(frozen=True, kw_only=True)
class CompleteMaintenance:
    actor_id: int
    maintenance_record_id: int


class CompleteMaintenanceHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def handle(self, command: CompleteMaintenance) -> None:
        with self.uow:
            require_role(self.uow, command.actor_id, UserRole.TECHNICIAN)
            record = self.uow.maintenance_records.get(command.maintenance_record_id)
            if record is None:
                raise NotFoundError("Bakım kaydı bulunamadı.")
            device = get_device_or_raise(self.uow, record.device_id)

            record.complete(device)

            self.uow.maintenance_records.update(record)
            self.uow.devices.update(device)
            self.uow.add_event(
                MaintenanceCompleted(maintenance_record_id=record.id, device_id=device.id)
            )
            self.uow.commit()
