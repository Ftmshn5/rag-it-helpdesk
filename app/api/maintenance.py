"""Bakım kaydı endpoint'leri (yazma tarafı)."""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.schemas import CreatedResponse
from app.application.commands.maintenance import (
    CompleteMaintenanceCommand,
    CompleteMaintenanceHandler,
    StartMaintenanceCommand,
    StartMaintenanceHandler,
)
from app.core.dependencies import (
    get_complete_maintenance_handler,
    get_current_user_id,
    get_start_maintenance_handler,
)
from app.domain.enums import MaintenanceType

router = APIRouter(tags=["maintenance"])


class StartMaintenanceRequest(BaseModel):
    type: MaintenanceType
    description: str = Field(min_length=1, max_length=2000)
    ticket_id: int | None = None


@router.post(
    "/devices/{device_id}/maintenance-records",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedResponse,
)
def start_maintenance(
    device_id: int,
    body: StartMaintenanceRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: StartMaintenanceHandler = Depends(get_start_maintenance_handler),
) -> CreatedResponse:
    record_id = handler.handle(
        StartMaintenanceCommand(actor_id=actor_id, device_id=device_id, **body.model_dump())
    )
    return CreatedResponse(id=record_id)


@router.post(
    "/maintenance-records/{maintenance_record_id}/complete",
    status_code=status.HTTP_204_NO_CONTENT,
)
def complete_maintenance(
    maintenance_record_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: CompleteMaintenanceHandler = Depends(get_complete_maintenance_handler),
) -> None:
    handler.handle(
        CompleteMaintenanceCommand(actor_id=actor_id, maintenance_record_id=maintenance_record_id)
    )
