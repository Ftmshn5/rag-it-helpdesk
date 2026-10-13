"""Domain hataları: her iş kuralı ihlalinin kendi sınıfı vardır.

Hiyerarşi (kalıtım): hepsi DomainError'dan türer; ara sınıflar (DeviceError,
MaintenanceError, TicketError) hatanın hangi kavrama ait olduğunu söyler.

    DomainError
    ├── DeviceError ─ DeviceAlreadyAssignedError, DeviceInMaintenanceError, ...
    ├── AssignmentAlreadyClosedError
    ├── MaintenanceError ─ MaintenanceAlreadyOpenError, ...
    ├── TicketError ─ InvalidTicketTransitionError, InvalidAssigneeError, ...
    └── InvalidFileError

Faydası: API katmanı tek bir taban sınıfı (DomainError → 409) HTTP koduna
çevirir; testler ve çağıran kod ise hangi kuralın ihlal edildiğini türünden
anlar (mesaj metnine bakmadan). Her sınıfın varsayılan Türkçe mesajı vardır;
gerekirse daha ayrıntılı bir mesajla oluşturulabilir.
"""


class DomainError(Exception):
    """Tüm iş kuralı ihlallerinin ortak tabanı. Mesajlar kullanıcıya gösterilir (Türkçe)."""

    default_message = "İş kuralı ihlal edildi."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)


# --- Cihaz (iş kuralları 1, 6, 7, 9) ---


class DeviceError(DomainError):
    """Cihazın mevcut durumu istenen işleme izin vermiyor."""


class DeviceAlreadyAssignedError(DeviceError):
    default_message = "Cihaz zaten zimmetli. Önce iade alınmalı."


class DeviceInMaintenanceError(DeviceError):
    default_message = "Cihaz bakımda, bu işlem yapılamaz."


class DeviceRetiredError(DeviceError):
    default_message = "Hurdaya ayrılmış cihazla bu işlem yapılamaz."


class DeviceNotAssignedError(DeviceError):
    default_message = "Cihaz zimmetli değil."


class DeviceNotInStockError(DeviceError):
    default_message = "Yalnızca depodaki cihazla bu işlem yapılabilir."


class DuplicateDeviceError(DeviceError):
    """Demirbaş veya seri numarası başka bir cihazda kayıtlı (cihaz kimliği benzersizdir)."""

    default_message = "Bu cihaz zaten kayıtlı."


class AssignmentAlreadyClosedError(DomainError):
    default_message = "Bu zimmet zaten iade alınmış."


# --- Bakım (iş kuralları 2, 8) ---


class MaintenanceError(DomainError):
    """Bakım kaydıyla ilgili kural ihlali."""


class MaintenanceAlreadyOpenError(MaintenanceError):
    default_message = "Cihazın zaten açık bir bakım kaydı var."


class MaintenanceAlreadyCompletedError(MaintenanceError):
    default_message = "Bu bakım kaydı zaten tamamlanmış."


class DeviceNotInMaintenanceError(MaintenanceError):
    default_message = "Cihaz bakımda değil."


class MaintenanceDeviceMismatchError(MaintenanceError):
    default_message = "Bakım kaydı bu cihaza ait değil."


# --- Talep (iş kuralları 3, 5, 11 ve durum geçişleri) ---


class TicketError(DomainError):
    """Talebin durumu veya tarafları istenen işleme izin vermiyor."""


class InvalidTicketTransitionError(TicketError):
    """State deseni: talebin mevcut durumunda bu geçiş tanımlı değil."""

    default_message = "Talebin mevcut durumunda bu işlem yapılamaz."


class InvalidAssigneeError(TicketError):
    default_message = "Talep yalnızca teknisyen rolündeki kullanıcıya atanabilir."


class TicketClosedError(TicketError):
    default_message = "Kapanmış talebe ek veya not eklenemez."


class UrgencyChangeNotAllowedError(TicketError):
    default_message = "Çözülmüş veya kapanmış talebin aciliyeti değiştirilemez."


class AiAnswerAlreadyEvaluatedError(TicketError):
    default_message = "Bu AI yanıtı zaten değerlendirilmiş."


# --- Dosya (iş kuralı 5) ---


class InvalidFileError(DomainError):
    """Yüklenen dosya kurallara uymuyor (tür veya boyut). Durum çatışması değil, geçersiz veridir."""

    default_message = "Geçersiz dosya."
