"""Domain hata hiyerarşisi: her kural ihlali kendi sınıfını fırlatır, hepsi DomainError'dur."""

import inspect

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.domain import errors
from app.domain.enums import DeviceStatus, MaintenanceType, TicketCategory, TicketStatus, UserRole
from app.domain.errors import (
    AiAnswerAlreadyEvaluatedError,
    AssignmentAlreadyClosedError,
    DeviceAlreadyAssignedError,
    DeviceError,
    DeviceInMaintenanceError,
    DeviceNotAssignedError,
    DeviceNotInMaintenanceError,
    DeviceNotInStockError,
    DeviceRetiredError,
    DomainError,
    InvalidAssigneeError,
    InvalidFileError,
    InvalidTicketTransitionError,
    MaintenanceAlreadyCompletedError,
    MaintenanceDeviceMismatchError,
    MaintenanceError,
    TicketClosedError,
    TicketError,
    UrgencyChangeNotAllowedError,
)
from app.domain.inventory import Assignment, Device, MaintenanceRecord
from app.domain.ticket import AIResponse, Ticket
from app.domain.user import User
from app.main import create_app


def device(status: DeviceStatus = DeviceStatus.IN_STOCK, device_id: int = 1) -> Device:
    return Device(id=device_id, asset_tag="PC-1", type="PC", brand="Dell", model="X", serial_number="S1", status=status)


def ticket(status: TicketStatus = TicketStatus.OPEN) -> Ticket:
    return Ticket(title="t", description="d", category=TicketCategory.HARDWARE, requester_id=1, status=status)


# --- Hiyerarşi ---


def test_every_domain_error_class_derives_from_domain_error():
    classes = [c for _, c in inspect.getmembers(errors, inspect.isclass) if issubclass(c, Exception)]
    assert len(classes) > 15
    assert all(issubclass(c, DomainError) for c in classes)


@pytest.mark.parametrize(
    "error_class, group",
    [
        (DeviceAlreadyAssignedError, DeviceError),
        (DeviceNotInStockError, DeviceError),
        (MaintenanceAlreadyCompletedError, MaintenanceError),
        (InvalidTicketTransitionError, TicketError),
        (InvalidAssigneeError, TicketError),
    ],
)
def test_specific_errors_belong_to_their_concept_group(error_class, group):
    assert issubclass(error_class, group)


def test_default_message_is_turkish_and_can_be_overridden():
    assert str(DeviceNotAssignedError()) == "Cihaz zimmetli değil."
    assert str(DeviceNotAssignedError("Cihazın aktif bir zimmeti yok.")) == "Cihazın aktif bir zimmeti yok."


# --- Kural → hata türü ---


@pytest.mark.parametrize(
    "status, error_class",
    [
        (DeviceStatus.ASSIGNED, DeviceAlreadyAssignedError),
        (DeviceStatus.IN_REPAIR, DeviceInMaintenanceError),
        (DeviceStatus.RETIRED, DeviceRetiredError),
    ],
)
def test_assigning_unavailable_device_raises_status_specific_error(status, error_class):
    with pytest.raises(error_class):
        device(status).assign()


def test_device_rule_errors():
    with pytest.raises(DeviceInMaintenanceError):
        device(DeviceStatus.IN_REPAIR).mark_returned()
    with pytest.raises(DeviceNotAssignedError):
        device(DeviceStatus.IN_STOCK).mark_returned()
    with pytest.raises(DeviceNotInStockError):
        device(DeviceStatus.ASSIGNED).retire()
    with pytest.raises(DeviceNotInMaintenanceError):
        device(DeviceStatus.IN_STOCK).finish_maintenance(DeviceStatus.IN_STOCK)


def test_assignment_and_maintenance_errors():
    assignment = Assignment(device_id=1, user_id=2, assigned_by=3)
    assignment.close()
    with pytest.raises(AssignmentAlreadyClosedError):
        assignment.close()

    record = MaintenanceRecord.open(device=device(), technician_id=4, type=MaintenanceType.REPAIR, description="-")
    with pytest.raises(MaintenanceDeviceMismatchError):
        record.complete(device(DeviceStatus.IN_REPAIR, device_id=99))


def test_ticket_rule_errors():
    with pytest.raises(InvalidTicketTransitionError):
        ticket(TicketStatus.OPEN).close()
    with pytest.raises(InvalidAssigneeError):
        ticket(TicketStatus.ESCALATED).assign(User(id=5, full_name="A", email="a@x", role=UserRole.USER))
    with pytest.raises(TicketClosedError):
        ticket(TicketStatus.CLOSED).ensure_open_for_contributions()
    with pytest.raises(UrgencyChangeNotAllowedError):
        ticket(TicketStatus.RESOLVED).set_urgent(True)

    response = AIResponse(ticket_id=1, answer="a", confidence=0.9)
    response.record_feedback(True)
    with pytest.raises(AiAnswerAlreadyEvaluatedError):
        response.record_feedback(False)


# --- HTTP eşlemesi: alt sınıflar da doğru koda düşer ---


def test_any_domain_error_maps_to_409_and_invalid_file_to_422():
    app = create_app()
    router = APIRouter()

    @router.get("/_conflict")
    def conflict() -> None:
        raise DeviceAlreadyAssignedError()

    @router.get("/_invalid_file")
    def invalid_file() -> None:
        raise InvalidFileError("Dosya boş.")

    app.include_router(router)
    client = TestClient(app)

    response = client.get("/_conflict")
    assert response.status_code == 409
    assert response.json() == {"detail": "Cihaz zaten zimmetli. Önce iade alınmalı."}
    assert client.get("/_invalid_file").status_code == 422
