"""Cihaz endpoint'leri (yazma tarafı).

CQRS gereği command endpoint'leri veri döndürmez: oluşturma yalnızca yeni
kaydın id'sini, güncellemeler 204 (içerik yok) döndürür. Güncel veriyi okumak
okuma tarafının (queries) işidir.
"""

from datetime import date

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.application.commands.assignments import (
    AssignDevice,
    AssignDeviceHandler,
    ReturnDevice,
    ReturnDeviceHandler,
)
from app.application.commands.devices import (
    RegisterDevice,
    RegisterDeviceHandler,
    RetireDevice,
    RetireDeviceHandler,
    UpdateDeviceDetails,
    UpdateDeviceDetailsHandler,
)
from app.core.dependencies import (
    get_assign_device_handler,
    get_current_user_id,
    get_register_device_handler,
    get_retire_device_handler,
    get_return_device_handler,
    get_update_device_details_handler,
)

router = APIRouter(prefix="/devices", tags=["devices"])


class RegisterDeviceRequest(BaseModel):
    asset_tag: str = Field(min_length=1, max_length=50, examples=["PC-0100"])
    type: str = Field(min_length=1, max_length=50, examples=["Masaüstü"])
    brand: str = Field(min_length=1, max_length=80, examples=["Dell"])
    model: str = Field(min_length=1, max_length=120, examples=["OptiPlex 7010"])
    serial_number: str = Field(min_length=1, max_length=120, examples=["DL7010-XYZ1"])
    location: str | None = Field(default=None, max_length=120)
    purchase_date: date | None = None


class UpdateDeviceDetailsRequest(BaseModel):
    type: str | None = Field(default=None, min_length=1, max_length=50)
    brand: str | None = Field(default=None, min_length=1, max_length=80)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, min_length=1, max_length=120)
    purchase_date: date | None = None


class AssignDeviceRequest(BaseModel):
    user_id: int


class CreatedResponse(BaseModel):
    id: int


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatedResponse)
def register_device(
    body: RegisterDeviceRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: RegisterDeviceHandler = Depends(get_register_device_handler),
) -> CreatedResponse:
    device_id = handler.handle(RegisterDevice(actor_id=actor_id, **body.model_dump()))
    return CreatedResponse(id=device_id)


@router.patch("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_device_details(
    device_id: int,
    body: UpdateDeviceDetailsRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: UpdateDeviceDetailsHandler = Depends(get_update_device_details_handler),
) -> None:
    handler.handle(
        UpdateDeviceDetails(actor_id=actor_id, device_id=device_id, **body.model_dump())
    )


@router.post("/{device_id}/retire", status_code=status.HTTP_204_NO_CONTENT)
def retire_device(
    device_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: RetireDeviceHandler = Depends(get_retire_device_handler),
) -> None:
    handler.handle(RetireDevice(actor_id=actor_id, device_id=device_id))


@router.post(
    "/{device_id}/assignments",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedResponse,
)
def assign_device(
    device_id: int,
    body: AssignDeviceRequest,
    actor_id: int = Depends(get_current_user_id),
    handler: AssignDeviceHandler = Depends(get_assign_device_handler),
) -> CreatedResponse:
    assignment_id = handler.handle(
        AssignDevice(actor_id=actor_id, device_id=device_id, user_id=body.user_id)
    )
    return CreatedResponse(id=assignment_id)


@router.post("/{device_id}/return", status_code=status.HTTP_204_NO_CONTENT)
def return_device(
    device_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: ReturnDeviceHandler = Depends(get_return_device_handler),
) -> None:
    handler.handle(ReturnDevice(actor_id=actor_id, device_id=device_id))
