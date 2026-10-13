"""Envanter modülünün varlıkları: cihaz, zimmet ve bakım kaydı.

Zengin domain modeli: iş kuralları bu sınıfların metotlarındadır. Alanlar
korumalıdır (`_`); dışarıdan yalnızca okunur. Cihazın durumu hiçbir zaman
doğrudan atanmaz (iş kuralı 6), yalnızca iş akışı metotlarıyla değişir:
assign_to / return_from / start_maintenance / finish_maintenance / retire.
"""

from datetime import date, datetime

from app.domain.clock import Clock
from app.domain.entity import Entity
from app.domain.enums import DeviceStatus, MaintenanceType
from app.domain.errors import (
    AssignmentAlreadyClosedError,
    DeviceAlreadyAssignedError,
    DeviceError,
    DeviceInMaintenanceError,
    DeviceNotAssignedError,
    DeviceNotInMaintenanceError,
    DeviceNotInStockError,
    DeviceRetiredError,
    MaintenanceAlreadyCompletedError,
    MaintenanceAlreadyOpenError,
    MaintenanceDeviceMismatchError,
)
from app.domain.user import User


class Assignment(Entity):
    """Bir cihazın bir kullanıcıya zimmeti. returned_at boşsa zimmet aktiftir.

    Yeni zimmet yalnızca Device.assign_to() ile oluşur; kapatma da cihaz
    üzerinden (Device.return_from) yapılır ki cihaz durumu ile zimmet kaydı
    birbirinden kopmasın.
    """

    def __init__(
        self,
        *,
        id: int | None = None,
        device_id: int,
        user_id: int,
        assigned_by: int,
        assigned_at: datetime | None = None,
        returned_at: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self._device_id = device_id
        self._user_id = user_id
        self._assigned_by = assigned_by
        self._assigned_at = assigned_at or Clock.now()
        self._returned_at = returned_at

    @property
    def device_id(self) -> int:
        return self._device_id

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def assigned_by(self) -> int:
        return self._assigned_by

    @property
    def assigned_at(self) -> datetime:
        return self._assigned_at

    @property
    def returned_at(self) -> datetime | None:
        return self._returned_at

    @property
    def is_active(self) -> bool:
        return self._returned_at is None

    def close(self) -> None:
        """Zimmeti iade alınmış olarak kapatır. Kayıt silinmez; geçmiş korunur."""
        if not self.is_active:
            raise AssignmentAlreadyClosedError()
        self._returned_at = Clock.now()


# Zimmetlenemeyen her durumun kendi hata sınıfı ve duruma özgü mesajı
UNAVAILABLE_FOR_ASSIGNMENT: dict[DeviceStatus, tuple[type[DeviceError], str]] = {
    DeviceStatus.ASSIGNED: (DeviceAlreadyAssignedError, "Cihaz zaten zimmetli. Önce iade alınmalı."),
    DeviceStatus.IN_REPAIR: (DeviceInMaintenanceError, "Cihaz bakımda, zimmetlenemez."),
    DeviceStatus.RETIRED: (DeviceRetiredError, "Hurdaya ayrılmış cihaz zimmetlenemez."),
}


class Device(Entity):
    """Cihaz. Durum geçiş kuralları (iş kuralları 1, 2, 6-9) tek bir yerde korunur."""

    def __init__(
        self,
        *,
        id: int | None = None,
        asset_tag: str,
        type: str,
        brand: str,
        model: str,
        serial_number: str,
        status: DeviceStatus = DeviceStatus.IN_STOCK,
        location: str | None = None,
        purchase_date: date | None = None,
    ) -> None:
        super().__init__(id)
        self._asset_tag = asset_tag
        self._type = type
        self._brand = brand
        self._model = model
        self._serial_number = serial_number
        self._status = status
        self._location = location
        self._purchase_date = purchase_date

    # --- Okuma ---

    @property
    def asset_tag(self) -> str:
        return self._asset_tag

    @property
    def type(self) -> str:
        return self._type

    @property
    def brand(self) -> str:
        return self._brand

    @property
    def model(self) -> str:
        return self._model

    @property
    def serial_number(self) -> str:
        return self._serial_number

    @property
    def status(self) -> DeviceStatus:
        return self._status

    @property
    def location(self) -> str | None:
        return self._location

    @property
    def purchase_date(self) -> date | None:
        return self._purchase_date

    # --- Davranış ---

    def update_details(
        self,
        *,
        type: str | None = None,
        brand: str | None = None,
        model: str | None = None,
        location: str | None = None,
        purchase_date: date | None = None,
    ) -> None:
        """Tanımlayıcı olmayan bilgileri günceller; None verilen alan değişmez.

        asset_tag ve serial_number cihazın kimliğidir, güncellenmez. Durum bilerek
        burada yok: yalnızca iş akışlarıyla değişir (iş kuralı 6).
        """
        if type is not None:
            self._type = type
        if brand is not None:
            self._brand = brand
        if model is not None:
            self._model = model
        if location is not None:
            self._location = location
        if purchase_date is not None:
            self._purchase_date = purchase_date

    def assign_to(self, user: User, *, assigned_by: User) -> Assignment:
        """Cihazı kullanıcıya zimmetler ve zimmet kaydını üretir (iş kuralları 1, 7).

        Yalnızca depodaki cihaz zimmetlenebilir; diğer her durumun kendi hatası vardır.
        """
        if self._status != DeviceStatus.IN_STOCK:
            error_class, message = UNAVAILABLE_FOR_ASSIGNMENT[self._status]
            raise error_class(message)
        self._status = DeviceStatus.ASSIGNED
        return Assignment(device_id=self.id, user_id=user.id, assigned_by=assigned_by.id)

    def return_from(self, assignment: Assignment) -> None:
        """Zimmeti iade alır: zimmet kaydı kapanır, cihaz depoya döner."""
        if self._status == DeviceStatus.IN_REPAIR:
            # İade edilirse bakım bitince cihaz "önceki durum" olan ASSIGNED'a
            # döner ama ortada zimmet kalmaz; tutarsızlığı baştan engelliyoruz (iş kuralı 9).
            raise DeviceInMaintenanceError("Cihaz bakımda. Önce bakımı tamamlayın, sonra iade alın.")
        if self._status != DeviceStatus.ASSIGNED:
            raise DeviceNotAssignedError()
        if assignment.device_id != self.id:
            raise DeviceNotAssignedError("Zimmet kaydı bu cihaza ait değil.")
        assignment.close()
        self._status = DeviceStatus.IN_STOCK

    def retire(self) -> None:
        """Cihazı hurdaya ayırır (iş kuralı 7: yalnızca depodaki cihaz)."""
        if self._status == DeviceStatus.RETIRED:
            raise DeviceRetiredError("Cihaz zaten hurdaya ayrılmış.")
        if self._status != DeviceStatus.IN_STOCK:
            raise DeviceNotInStockError(
                "Yalnızca depodaki cihazlar hurdaya ayrılabilir. "
                "Önce zimmeti iade alın veya bakımı tamamlayın."
            )
        self._status = DeviceStatus.RETIRED

    def start_maintenance(self) -> DeviceStatus:
        """Cihazı bakıma alır ve bakım öncesi durumunu döndürür.

        Doğrudan değil, MaintenanceRecord.open() üzerinden çağrılır; böylece
        önceki durum mutlaka bakım kaydına yazılır.
        """
        if self._status == DeviceStatus.RETIRED:
            raise DeviceRetiredError("Hurdaya ayrılmış cihaza bakım kaydı açılamaz.")
        if self._status == DeviceStatus.IN_REPAIR:
            raise MaintenanceAlreadyOpenError()
        previous_status = self._status
        self._status = DeviceStatus.IN_REPAIR
        return previous_status

    def finish_maintenance(self, restore_to: DeviceStatus) -> None:
        """Bakımı bitirir; cihaz bakım öncesi durumuna döner (MaintenanceRecord.complete çağırır)."""
        if self._status != DeviceStatus.IN_REPAIR:
            raise DeviceNotInMaintenanceError()
        self._status = restore_to


class MaintenanceRecord(Entity):
    """Cihaz bakım kaydı. completed_at boşsa bakım sürüyor demektir.

    previous_device_status, bakım bitince cihazın döneceği durumu saklar
    (iş kuralı 2: bakım kapanınca cihaz önceki durumuna döner).
    """

    def __init__(
        self,
        *,
        id: int | None = None,
        device_id: int,
        technician_id: int,
        ticket_id: int | None = None,
        type: MaintenanceType,
        description: str,
        previous_device_status: DeviceStatus,
        performed_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        super().__init__(id)
        self._device_id = device_id
        self._technician_id = technician_id
        self._ticket_id = ticket_id
        self._type = type
        self._description = description
        self._previous_device_status = previous_device_status
        self._performed_at = performed_at or Clock.now()
        self._completed_at = completed_at

    @classmethod
    def open(
        cls,
        *,
        device: Device,
        technician_id: int,
        type: MaintenanceType,
        description: str,
        ticket_id: int | None = None,
    ) -> "MaintenanceRecord":
        """Factory Method: iş kuralı 2'nin ilk yarısı — cihaz IN_REPAIR olur, önceki durumu kayda yazılır.

        Yeni bakım kaydı oluşturmanın tek yolu budur; önceki durumu ayrıca hatırlamaya gerek kalmaz.
        """
        previous_status = device.start_maintenance()
        return cls(
            device_id=device.id,
            technician_id=technician_id,
            ticket_id=ticket_id,
            type=type,
            description=description,
            previous_device_status=previous_status,
        )

    @property
    def device_id(self) -> int:
        return self._device_id

    @property
    def technician_id(self) -> int:
        return self._technician_id

    @property
    def ticket_id(self) -> int | None:
        return self._ticket_id

    @property
    def type(self) -> MaintenanceType:
        return self._type

    @property
    def description(self) -> str:
        return self._description

    @property
    def previous_device_status(self) -> DeviceStatus:
        return self._previous_device_status

    @property
    def performed_at(self) -> datetime:
        return self._performed_at

    @property
    def completed_at(self) -> datetime | None:
        return self._completed_at

    @property
    def is_open(self) -> bool:
        return self._completed_at is None

    def complete(self, device: Device) -> None:
        """İş kuralı 2'nin ikinci yarısı: cihaz bakım öncesi durumuna döner."""
        if not self.is_open:
            raise MaintenanceAlreadyCompletedError()
        if device.id != self._device_id:
            raise MaintenanceDeviceMismatchError()
        device.finish_maintenance(restore_to=self._previous_device_status)
        self._completed_at = Clock.now()
