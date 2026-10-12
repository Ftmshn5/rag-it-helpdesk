"""Unit of Work deseni.

Bir iş akışında yapılan tüm değişiklikleri tek bir transaction'da toplar:
ya hepsi kaydedilir (commit) ya hiçbiri (rollback). Örneğin cihaz zimmetlerken
hem Assignment eklenir hem Device durumu değişir; ikisi birlikte olmalıdır.

Kullanım (command handler içinde):

    with self.uow:
        device = self.uow.devices.get(device_id)
        ...
        self.uow.add_event(DeviceAssigned(...))
        self.uow.commit()

`with` bloğundan commit edilmeden çıkılırsa (hata dahil) değişiklikler geri alınır.
Transaction sınırı böylece iş mantığında açıkça görünür ve application katmanı
SQLAlchemy Session'ını hiç tanımaz.

Olaylar: handler'ın eklediği olaylar commit BAŞARILI olduktan sonra event bus'a
yayınlanır; rollback olursa atılır. Böylece hiç gerçekleşmemiş bir değişiklik
için bildirim gönderilmez veya read model güncellenmez.
"""

from abc import ABC, abstractmethod
from typing import Self

from app.application.interfaces.event_bus import EventBus
from app.application.interfaces.repositories import (
    AssignmentRepository,
    DeviceRepository,
    MaintenanceRecordRepository,
    TicketAttachmentRepository,
    TicketRepository,
    UserRepository,
)
from app.domain.events import DomainEvent


class UnitOfWork(ABC):
    users: UserRepository
    devices: DeviceRepository
    assignments: AssignmentRepository
    maintenance_records: MaintenanceRecordRepository
    tickets: TicketRepository
    ticket_attachments: TicketAttachmentRepository

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self._pending_events: list[DomainEvent] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        # commit edilmiş bir transaction'da rollback etkisizdir; edilmemişse her şey geri alınır
        self.rollback()

    def add_event(self, event: DomainEvent) -> None:
        """Olayı commit sonrasında yayınlanmak üzere sıraya koyar."""
        self._pending_events.append(event)

    # Template Method: commit/rollback'in akışı burada sabit; veritabanına
    # özgü kısım (_commit/_rollback) alt sınıflarda doldurulur.

    def commit(self) -> None:
        self._commit()
        events, self._pending_events = self._pending_events, []
        for event in events:
            self.event_bus.publish(event)

    def rollback(self) -> None:
        self._pending_events.clear()
        self._rollback()

    @abstractmethod
    def _commit(self) -> None: ...

    @abstractmethod
    def _rollback(self) -> None: ...
