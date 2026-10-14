"""Ticket endpoint'leri (yazma tarafı)."""

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel, Field

from app.api.schemas import CreatedResponse
from app.application.commands.ai_answers import EvaluateAiAnswerCommand, EvaluateAiAnswerHandler
from app.application.commands.attachments import AttachScreenshotCommand, AttachScreenshotHandler
from app.application.commands.ticket_workflow import (
    AddCommentCommand,
    AddCommentHandler,
    AssignTicketCommand,
    AssignTicketHandler,
    CloseTicketCommand,
    CloseTicketHandler,
    EscalateTicketCommand,
    EscalateTicketHandler,
    MoveTicketCommand,
    MoveTicketHandler,
    ReopenTicketCommand,
    ReopenTicketHandler,
    ResolveTicketCommand,
    ResolveTicketHandler,
    StartWorkCommand,
    StartWorkHandler,
)
from app.application.commands.tickets import (
    CreateTicketCommand,
    CreateTicketHandler,
    SetTicketUrgencyCommand,
    SetTicketUrgencyHandler,
)
from app.core.config import get_settings
from app.core.dependencies import (
    get_add_comment_handler,
    get_assign_ticket_handler,
    get_attach_screenshot_handler,
    get_close_ticket_handler,
    get_create_ticket_handler,
    get_current_user_id,
    get_escalate_ticket_handler,
    get_evaluate_ai_answer_handler,
    get_move_ticket_handler,
    get_reopen_ticket_handler,
    get_resolve_ticket_handler,
    get_set_ticket_urgency_handler,
    get_start_work_handler,
)
from app.domain.enums import TicketCategory, TicketStatus

router = APIRouter(prefix="/tickets", tags=["tickets"])


class CreateTicketRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200, examples=["Yazıcı çıktı vermiyor"])
    description: str = Field(min_length=1, max_length=5000)
    category: TicketCategory
    is_urgent: bool = False
    device_id: int | None = None


class SetTicketUrgencyRequest(BaseModel):
    is_urgent: bool


class AssignTicketRequest(BaseModel):
    technician_id: int


class EvaluateAiAnswerRequest(BaseModel):
    is_helpful: bool


class MoveTicketRequest(BaseModel):
    status: TicketStatus


class EscalateTicketRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000, examples=["Anakart arızası, parça değişimi gerekiyor"])


class AddCommentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatedResponse)
def create_ticket(
    body: CreateTicketRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: CreateTicketHandler = Depends(get_create_ticket_handler),
) -> CreatedResponse:
    ticket_id = handler.handle(CreateTicketCommand(actor_id=actor_id, **body.model_dump()))
    return CreatedResponse(id=ticket_id)


@router.put("/{ticket_id}/urgency", status_code=status.HTTP_204_NO_CONTENT)
def set_ticket_urgency(
    ticket_id: int,
    body: SetTicketUrgencyRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: SetTicketUrgencyHandler = Depends(get_set_ticket_urgency_handler),
) -> None:
    handler.handle(
        SetTicketUrgencyCommand(actor_id=actor_id, ticket_id=ticket_id, is_urgent=body.is_urgent)
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
        AttachScreenshotCommand(actor_id=actor_id, ticket_id=ticket_id, content=content)
    )
    return CreatedResponse(id=attachment_id)


# --- Durum geçişleri (State) ---


@router.post("/{ticket_id}/assign", status_code=status.HTTP_204_NO_CONTENT)
def assign_ticket(
    ticket_id: int,
    body: AssignTicketRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: AssignTicketHandler = Depends(get_assign_ticket_handler),
) -> None:
    handler.handle(
        AssignTicketCommand(actor_id=actor_id, ticket_id=ticket_id, technician_id=body.technician_id)
    )


@router.post("/{ticket_id}/start", status_code=status.HTTP_204_NO_CONTENT)
def start_work(
    ticket_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: StartWorkHandler = Depends(get_start_work_handler),
) -> None:
    handler.handle(StartWorkCommand(actor_id=actor_id, ticket_id=ticket_id))


@router.post("/{ticket_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
def resolve_ticket(
    ticket_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: ResolveTicketHandler = Depends(get_resolve_ticket_handler),
) -> None:
    handler.handle(ResolveTicketCommand(actor_id=actor_id, ticket_id=ticket_id))


@router.post("/{ticket_id}/close", status_code=status.HTTP_204_NO_CONTENT)
def close_ticket(
    ticket_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: CloseTicketHandler = Depends(get_close_ticket_handler),
) -> None:
    handler.handle(CloseTicketCommand(actor_id=actor_id, ticket_id=ticket_id))


@router.post("/{ticket_id}/reopen", status_code=status.HTTP_204_NO_CONTENT)
def reopen_ticket(
    ticket_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: ReopenTicketHandler = Depends(get_reopen_ticket_handler),
) -> None:
    handler.handle(ReopenTicketCommand(actor_id=actor_id, ticket_id=ticket_id))


@router.post("/{ticket_id}/move", status_code=status.HTTP_204_NO_CONTENT)
def move_ticket(
    ticket_id: int,
    body: MoveTicketRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: MoveTicketHandler = Depends(get_move_ticket_handler),
) -> None:
    """Kanban: talebi hedef duruma taşır; geçersiz geçişte 409 ve State'in mesajı döner."""
    handler.handle(MoveTicketCommand(actor_id=actor_id, ticket_id=ticket_id, target_status=body.status))


@router.post("/{ticket_id}/escalate", status_code=status.HTTP_204_NO_CONTENT)
def escalate_ticket(
    ticket_id: int,
    body: EscalateTicketRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: EscalateTicketHandler = Depends(get_escalate_ticket_handler),
) -> None:
    """UC-07: atanan teknisyen talebi bir üst destek seviyesine eskale eder."""
    handler.handle(EscalateTicketCommand(actor_id=actor_id, ticket_id=ticket_id, reason=body.reason))


# --- Not ---


@router.post(
    "/{ticket_id}/comments",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedResponse,
)
def add_comment(
    ticket_id: int,
    body: AddCommentRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: AddCommentHandler = Depends(get_add_comment_handler),
) -> CreatedResponse:
    comment_id = handler.handle(
        AddCommentCommand(actor_id=actor_id, ticket_id=ticket_id, content=body.content)
    )
    return CreatedResponse(id=comment_id)


# --- UC-02: AI önerisini değerlendir ---


@router.post("/{ticket_id}/ai-feedback", status_code=status.HTTP_204_NO_CONTENT)
def evaluate_ai_answer(
    ticket_id: int,
    body: EvaluateAiAnswerRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: EvaluateAiAnswerHandler = Depends(get_evaluate_ai_answer_handler),
) -> None:
    handler.handle(
        EvaluateAiAnswerCommand(actor_id=actor_id, ticket_id=ticket_id, is_helpful=body.is_helpful)
    )
