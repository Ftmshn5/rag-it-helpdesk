"""Ekran görüntüsü command'ı (UC-15: talebe ekran görüntüsü ekle).

Dosya sistemi veritabanı transaction'ına dahil değildir: dosya diske yazılıp
veritabanı commit'i başarısız olursa, hiçbir kayda bağlı olmayan "yetim" bir
dosya kalır. Bunu önlemek için:
1. Tüm ucuz kontroller (yetki, tür, boyut) dosya yazılmadan ÖNCE yapılır.
2. Dosya yazıldıktan sonra bir hata olursa dosya geri silinir
   (telafi edici işlem / compensating action).
"""

from dataclasses import dataclass

from app.application.commands.base import ActorCommand, CommandHandler
from app.application.errors import PermissionDeniedError
from app.application.interfaces.file_storage import FileStorage
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.attachments import ScreenshotValidator
from app.domain.events import ScreenshotAttached
from app.domain.ticket import TicketAttachment


@dataclass(frozen=True, kw_only=True)
class AttachScreenshotCommand(ActorCommand):
    ticket_id: int
    content: bytes


class AttachScreenshotHandler(CommandHandler[AttachScreenshotCommand, int]):
    def __init__(self, uow: UnitOfWork, storage: FileStorage, validator: ScreenshotValidator) -> None:
        super().__init__(uow)
        self._storage = storage
        self._validator = validator

    def handle(self, command: AttachScreenshotCommand) -> int:
        with self._uow:
            actor = self._require_actor(command.actor_id)
            ticket = self._get_ticket(command.ticket_id)
            if not ticket.is_participant(actor):
                raise PermissionDeniedError("Bu talebe ek yükleme yetkiniz yok.")
            ticket.ensure_open_for_contributions()
            image_type = self._validator.validate(command.content)

            file_path = self._storage.save(
                command.content, folder=f"tickets/{ticket.id}", extension=image_type.extension
            )
            try:
                attachment = self._uow.ticket_attachments.add(
                    TicketAttachment(ticket_id=ticket.id, file_path=file_path, mime_type=image_type.mime_type)
                )
                self._uow.add_event(
                    ScreenshotAttached(ticket_id=ticket.id, attachment_id=attachment.id, uploaded_by=actor.id)
                )
                self._uow.commit()
            except Exception:
                self._storage.delete(file_path)
                raise
            return attachment.id
