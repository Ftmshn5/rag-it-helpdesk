"""Ticket endpoint'leri (yazma tarafı)."""

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel, Field

from app.api.schemas import CreatedResponse
from app.application.commands.attachments import AttachScreenshot, AttachScreenshotHandler
from app.application.commands.tickets import (
    CreateTicket,
    CreateTicketHandler,
    SetTicketUrgency,
    SetTicketUrgencyHandler,
)
from app.core.config import get_settings
from app.core.dependencies import (
    get_attach_screenshot_handler,
    get_create_ticket_handler,
    get_current_user_id,
    get_set_ticket_urgency_handler,
)
from app.domain.enums import TicketCategory

router = APIRouter(prefix="/tickets", tags=["tickets"])


class CreateTicketRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200, examples=["Yazıcı çıktı vermiyor"])
    description: str = Field(min_length=1, max_length=5000)
    category: TicketCategory
    is_urgent: bool = False
    device_id: int | None = None


class SetTicketUrgencyRequest(BaseModel):
    is_urgent: bool


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatedResponse)
def create_ticket(
    body: CreateTicketRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: CreateTicketHandler = Depends(get_create_ticket_handler),
) -> CreatedResponse:
    ticket_id = handler.handle(CreateTicket(actor_id=actor_id, **body.model_dump()))
    return CreatedResponse(id=ticket_id)


@router.put("/{ticket_id}/urgency", status_code=status.HTTP_204_NO_CONTENT)
def set_ticket_urgency(
    ticket_id: int,
    body: SetTicketUrgencyRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: SetTicketUrgencyHandler = Depends(get_set_ticket_urgency_handler),
) -> None:
    handler.handle(
        SetTicketUrgency(actor_id=actor_id, ticket_id=ticket_id, is_urgent=body.is_urgent)
    )


@router.post(
    "/{ticket_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedResponse,
)
def attach_screenshot(
    ticket_id: int,
    file: UploadFile = File(description="PNG veya JPG ekran görüntüsü"),
    actor_id: int = Depends(get_current_user_id),
    handler: AttachScreenshotHandler = Depends(get_attach_screenshot_handler),
) -> CreatedResponse:
    # Sınırın 1 bayt fazlası okunur: dosya ne kadar büyük olursa olsun belleğe
    # en fazla bu kadarı alınır; sınırı aştığını domain kuralı yakalar.
    content = file.file.read(get_settings().max_upload_size_bytes + 1)
    attachment_id = handler.handle(
        AttachScreenshot(actor_id=actor_id, ticket_id=ticket_id, content=content)
    )
    return CreatedResponse(id=attachment_id)
