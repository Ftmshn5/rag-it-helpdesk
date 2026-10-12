"""Envanter modülünün varlıkları: cihaz, zimmet ve bakım kaydı."""

from dataclasses import dataclass, field
from datetime import date, datetime

from app.domain.clock import utc_now
from app.domain.enums import DeviceStatus, MaintenanceType
from app.domain.errors import BusinessRuleViolation


UNAVAILABLE_FOR_ASSIGNMENT = {
    DeviceStatus.ASSIGNED: "Cihaz zaten zimmetli. Önce iade alınmalı.",
    DeviceStatus.IN_REPAIR: "Cihaz bakımda, zimmetlenemez.",
    DeviceStatus.RETIRED: "Hurdaya ayrılmış cihaz zimmetlenemez.",
}


@dataclass(kw_only=True)
class Device:
    """Cihaz. `status` alanı dışarıdan doğrudan değiştirilmez; yalnızca bu
    sınıfın iş akışı metotlarıyla (retire, ileride assign/return/bakım) değişir.
    Böylece durum geçiş kuralları tek bir yerde korunur.
    """

    id: int | None = None
    asset_tag: str
    type: str
    brand: str
    model: str
    serial_number: str
    status: DeviceStatus = DeviceStatus.IN_STOCK
    location: str | None = None
    purchase_date: date | None = None

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

        asset_tag ve serial_number cihazın kimliğidir, güncellenmez. status
        bilerek burada yok: durum yalnızca iş akışlarıyla değişir.
        """
        changes = {
            "type": type,
            "brand": brand,
            "model": model,
            "location": location,
            "purchase_date": purchase_date,
        }
        for name, value in changes.items():
            if value is not None:
                setattr(self, name, value)

    def assign(self) -> None:
        """Cihazı zimmetli duruma geçirir. Yalnızca depodaki cihaz zimmetlenebilir."""
        if self.status != DeviceStatus.IN_STOCK:
            raise BusinessRuleViolation(UNAVAILABLE_FOR_ASSIGNMENT[self.status])
        self.status = DeviceStatus.ASSIGNED

    def mark_returned(self) -> None:
        if self.status == DeviceStatus.IN_REPAIR:
            # İade edilirse bakım bitince cihaz "önceki durum" olan ASSIGNED'a
            # döner ama ortada zimmet kalmaz; tutarsızlığı baştan engelliyoruz.
            raise BusinessRuleViolation("Cihaz bakımda. Önce bakımı tamamlayın, sonra iade alın.")
        if self.status != DeviceStatus.ASSIGNED:
            raise BusinessRuleViolation("Cihaz zimmetli değil.")
        self.status = DeviceStatus.IN_STOCK

    def retire(self) -> None:
        if self.status == DeviceStatus.RETIRED:
            raise BusinessRuleViolation("Cihaz zaten hurdaya ayrılmış.")
        if self.status != DeviceStatus.IN_STOCK:
            raise BusinessRuleViolation(
                "Yalnızca depodaki cihazlar hurdaya ayrılabilir. "
                "Önce zimmeti iade alın veya bakımı tamamlayın."
            )
        self.status = DeviceStatus.RETIRED


@dataclass(kw_only=True)
class Assignment:
    """Bir cihazın bir kullanıcıya zimmeti. returned_at boşsa zimmet aktiftir."""

    id: int | None = None
    device_id: int
    user_id: int
    assigned_by: int
    assigned_at: datetime = field(default_factory=utc_now)
    returned_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.returned_at is None

    def close(self) -> None:
        """Zimmeti iade alınmış olarak kapatır. Kayıt silinmez; geçmiş korunur."""
        if not self.is_active:
            raise BusinessRuleViolation("Bu zimmet zaten iade alınmış.")
        self.returned_at = utc_now()


@dataclass(kw_only=True)
class MaintenanceRecord:
    """Cihaz bakım kaydı. completed_at boşsa bakım sürüyor demektir.

    previous_device_status, bakım bitince cihazın döneceği durumu saklar
    (iş kuralı 2: bakım kapanınca cihaz önceki durumuna döner).
    """

    id: int | None = None
    device_id: int
    technician_id: int
    ticket_id: int | None = None
    type: MaintenanceType
    description: str
    previous_device_status: DeviceStatus
    performed_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.completed_at is None
