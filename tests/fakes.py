"""Testler için in-memory (bellekte çalışan) repository ve Unit of Work sahteleri.

Command handler testleri bunlarla veritabanı olmadan, hızlıca çalışır.
Handler'lar yalnızca arayüzleri bildiği için gerçek ile sahte arasındaki fark
onlara görünmez — Repository deseninin test edilebilirlik faydası budur.
"""

from copy import deepcopy
from typing import Generic, TypeVar

from app.application.interfaces.event_bus import EventBus, EventHandler
from app.application.interfaces.repositories import (
    AssignmentRepository,
    DeviceRepository,
    MaintenanceRecordRepository,
    TicketRepository,
    UserRepository,
)
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.events import DomainEvent
from app.domain.inventory import Assignment, Device, MaintenanceRecord

E = TypeVar("E")


class InMemoryRepository(Generic[E]):
    def __init__(self) -> None:
        self.items: dict[int, E] = {}
        self._next_id = 1

    # Kopya döndürülür/saklanır: gerçek veritabanında olduğu gibi, nesne üzerinde
    # yapılan değişiklik update() çağrılmadan kalıcı olmamalı.
    def get(self, entity_id: int) -> E | None:
        item = self.items.get(entity_id)
        return deepcopy(item) if item else None

    def add(self, entity: E) -> E:
        entity.id = self._next_id
        self._next_id += 1
        self.items[entity.id] = deepcopy(entity)
        return entity

    def update(self, entity: E) -> None:
        if entity.id not in self.items:
            raise KeyError(entity.id)
        self.items[entity.id] = deepcopy(entity)

    def _first(self, predicate) -> E | None:
        for item in self.items.values():
            if predicate(item):
                return deepcopy(item)
        return None


class InMemoryUserRepository(InMemoryRepository, UserRepository):
    pass


class InMemoryDeviceRepository(InMemoryRepository[Device], DeviceRepository):
    def get_by_asset_tag(self, asset_tag: str) -> Device | None:
        return self._first(lambda device: device.asset_tag == asset_tag)


class InMemoryAssignmentRepository(InMemoryRepository[Assignment], AssignmentRepository):
    def get_active_for_device(self, device_id: int) -> Assignment | None:
        return self._first(lambda a: a.device_id == device_id and a.is_active)


class InMemoryMaintenanceRecordRepository(
    InMemoryRepository[MaintenanceRecord], MaintenanceRecordRepository
):
    def get_open_for_device(self, device_id: int) -> MaintenanceRecord | None:
        return self._first(lambda record: record.device_id == device_id and record.is_open)


class InMemoryTicketRepository(InMemoryRepository, TicketRepository):
    pass


class FakeEventBus(EventBus):
    """Yayınlanan olayları listede biriktirir; testler `published` üzerinden kontrol eder."""

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    def subscribe(self, event_type, handler: EventHandler) -> None:
        pass

    def publish(self, event: DomainEvent) -> None:
        self.published.append(event)


class FakeUnitOfWork(UnitOfWork):
    """Gerçek transaction yok; testler `committed` bayrağıyla commit edilip edilmediğini denetler."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        super().__init__(event_bus or FakeEventBus())
        self.users = InMemoryUserRepository()
        self.devices = InMemoryDeviceRepository()
        self.assignments = InMemoryAssignmentRepository()
        self.maintenance_records = InMemoryMaintenanceRecordRepository()
        self.tickets = InMemoryTicketRepository()
        self.committed = False

    def _commit(self) -> None:
        self.committed = True

    def _rollback(self) -> None:
        pass
