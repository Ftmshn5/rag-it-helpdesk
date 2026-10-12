"""Unit of Work deseni.

Bir iş akışında yapılan tüm değişiklikleri tek bir transaction'da toplar:
ya hepsi kaydedilir (commit) ya hiçbiri (rollback). Örneğin cihaz zimmetlerken
hem Assignment eklenir hem Device durumu değişir; ikisi birlikte olmalıdır.

Kullanım (command handler içinde):

    with self.uow:
        device = self.uow.devices.get(device_id)
        ...
        self.uow.commit()

`with` bloğundan commit edilmeden çıkılırsa (hata dahil) değişiklikler geri alınır.
Transaction sınırı böylece iş mantığında açıkça görünür ve application katmanı
SQLAlchemy Session'ını hiç tanımaz.
"""

from abc import ABC, abstractmethod
from typing import Self

from app.application.interfaces.repositories import (
    AssignmentRepository,
    DeviceRepository,
    MaintenanceRecordRepository,
    TicketRepository,
    UserRepository,
)


class UnitOfWork(ABC):
    users: UserRepository
    devices: DeviceRepository
    assignments: AssignmentRepository
    maintenance_records: MaintenanceRecordRepository
    tickets: TicketRepository

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        # commit edilmiş bir transaction'da rollback etkisizdir; edilmemişse her şey geri alınır
        self.rollback()

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
