"""Ekran görüntüsü command'ı (UC-15: talebe ekran görüntüsü ekle).

Dosya sistemi veritabanı transaction'ına dahil değildir: dosya diske yazılıp
veritabanı commit'i başarısız olursa, hiçbir kayda bağlı olmayan "yetim" bir
dosya kalır. Bunu önlemek için:
1. Tüm ucuz kontroller (yetki, tür, boyut) dosya yazılmadan ÖNCE yapılır.
2. Dosya yazıldıktan sonra bir hata olursa dosya geri silinir
   (telafi edici işlem / compensating action).
"""

from dataclasses import dataclass

from app.application.commands.common import ALL_ROLES, get_ticket_or_raise, require_role
from app.application.errors import PermissionDeniedError
from app.application.interfaces.file_storage import FileStorage
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.attachments import validate_screenshot
from app.domain.events import ScreenshotAttached
from app.domain.ticket import TicketAttachment


@dataclass(frozen=True, kw_only=True)
class AttachScreenshot:
    actor_id: int
    ticket_id: int
    content: bytes


class AttachScreenshotHandler:
    def __init__(self, uow: UnitOfWork, storage: FileStorage, max_size_bytes: int) -> None:
        self.uow = uow
        self.storage = storage
        self.max_size_bytes = max_size_bytes

    def handle(self, command: AttachScreenshot) -> int:
        with self.uow:
            actor = require_role(self.uow, command.actor_id, *ALL_ROLES)
            ticket = get_ticket_or_raise(self.uow, command.ticket_id)
            if not ticket.can_receive_attachment_from(actor):
                raise PermissionDeniedError("Bu talebe ek yükleme yetkiniz yok.")
            ticket.ensure_accepts_attachments()
            image_type = validate_screenshot(command.content, self.max_size_bytes)

            file_path = self.storage.save(
                command.content, folder=f"tickets/{ticket.id}", extension=image_type.extension
            )
            try:
                attachment = self.uow.ticket_attachments.add(
                    TicketAttachment(
                        ticket_id=ticket.id, file_path=file_path, mime_type=image_type.mime_type
                    )
                )
                self.uow.add_event(
                    ScreenshotAttached(
                        ticket_id=ticket.id, attachment_id=attachment.id, uploaded_by=actor.id
                    )
                )
                self.uow.commit()
            except Exception:
                self.storage.delete(file_path)
                raise
            return attachment.id
