"""Repository arayüzleri (Repository deseni).

Application katmanı veriye yalnızca bu soyutlamalar üzerinden erişir; verinin
PostgreSQL'de mi, bellekte mi durduğunu bilmez. Somut implementasyonlar
infrastructure/db içindedir, testlerde ise in-memory sahteleri kullanılır.

Burada yalnızca yazma tarafının (command handler'ların) ihtiyaç duyduğu
işlemler var. Listeler ve raporlar CQRS okuma tarafının (queries/) işidir.
Ek, yorum ve AI yanıtı repository'leri ilgili adımlarda eklenecek.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.domain.inventory import Assignment, Device, MaintenanceRecord
from app.domain.ticket import Ticket
from app.domain.user import User

E = TypeVar("E")


class Repository(ABC, Generic[E]):
    """Tüm repository'lerde ortak temel işlemler."""

    @abstractmethod
    def get(self, entity_id: int) -> E | None: ...

    @abstractmethod
    def add(self, entity: E) -> E:
        """Varlığı ekler ve veritabanının verdiği id ile birlikte döndürür."""

    @abstractmethod
    def update(self, entity: E) -> None: ...


class UserRepository(Repository[User], ABC):
    pass


class DeviceRepository(Repository[Device], ABC):
    @abstractmethod
    def get_by_asset_tag(self, asset_tag: str) -> Device | None: ...

    @abstractmethod
    def get_by_serial_number(self, serial_number: str) -> Device | None: ...


class AssignmentRepository(Repository[Assignment], ABC):
    @abstractmethod
    def get_active_for_device(self, device_id: int) -> Assignment | None:
        """Cihazın iade edilmemiş (aktif) zimmetini döndürür; yoksa None."""


class MaintenanceRecordRepository(Repository[MaintenanceRecord], ABC):
    @abstractmethod
    def get_open_for_device(self, device_id: int) -> MaintenanceRecord | None:
        """Cihazın tamamlanmamış bakım kaydını döndürür; yoksa None."""


class TicketRepository(Repository[Ticket], ABC):
    pass
