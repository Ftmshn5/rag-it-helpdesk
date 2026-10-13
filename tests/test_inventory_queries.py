"""Envanter okuma tarafı: device_inventory projektörü, sorgular ve API (gerçek PostgreSQL)."""

import pytest
from fastapi.testclient import TestClient

from app.application.commands.ai_answers import AutoAnswerTicketHandler
from app.application.commands.assignments import (
    AssignDeviceCommand,
    AssignDeviceHandler,
    ReturnDeviceCommand,
    ReturnDeviceHandler,
)
from app.application.commands.devices import RegisterDeviceCommand, RegisterDeviceHandler
from app.application.commands.maintenance import (
    CompleteMaintenanceCommand,
    CompleteMaintenanceHandler,
    StartMaintenanceCommand,
    StartMaintenanceHandler,
)
from app.application.errors import NotFoundError, PermissionDeniedError
from app.application.queries.inventory import (
    GetInventoryReportHandler,
    GetInventoryReportQuery,
    GetMaintenanceHistoryHandler,
    GetMaintenanceHistoryQuery,
)
from app.core.dependencies import get_db_session
from app.domain.enums import DeviceStatus, MaintenanceType, UserRole
from app.domain.user import User
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.db.projections import DeviceInventoryProjector
from app.infrastructure.db.queries import SqlInventoryQueries, SqlUserQueries
from app.infrastructure.db.read_models import DeviceInventoryModel
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from app.main import create_app
from tests.fakes import subscribe_all


@pytest.fixture
def setup(session_factory):
    """Gerçek event bus + envanter projektörü; yönetici, teknisyen ve kullanıcı."""
    bus = InMemoryEventBus()
    subscribe_all(
        bus,
        lambda: AutoAnswerTicketHandler(SqlAlchemyUnitOfWork(bus, session_factory), FakeAiSupport(), 0.6),
        projectors=(DeviceInventoryProjector(session_factory),),
    )
    uow = SqlAlchemyUnitOfWork(bus, session_factory)
    with uow:
        admin = uow.users.add(User(full_name="Envanter Yön.", email="inv.adm@test.edu", role=UserRole.ADMIN))
        tech = uow.users.add(
            User(full_name="Envanter Tek.", email="inv.tech@test.edu", role=UserRole.TECHNICIAN)
        )
        user = uow.users.add(
            User(full_name="Envanter Kul.", email="inv.user@test.edu", department="Fizik")
        )
        uow.commit()
    return uow, admin, tech, user


def inventory_row(session_factory, device_id) -> DeviceInventoryModel:
    with session_factory() as session:
        return session.get(DeviceInventoryModel, device_id)


def register(uow, admin, asset_tag="INV-0001", type_="Dizüstü") -> int:
    return RegisterDeviceHandler(uow).handle(
        RegisterDeviceCommand(
            actor_id=admin.id,
            asset_tag=asset_tag,
            type=type_,
            brand="Lenovo",
            model="T14",
            serial_number=f"SN-{asset_tag}",
        )
    )


# --- Olaylarla güncellenen read model ---


def test_inventory_row_follows_device_lifecycle(session_factory, setup):
    uow, admin, tech, user = setup

    device_id = register(uow, admin)
    row = inventory_row(session_factory, device_id)
    assert (row.status, row.holder_name, row.maintenance_count) == ("IN_STOCK", None, 0)

    AssignDeviceHandler(uow).handle(AssignDeviceCommand(actor_id=admin.id, device_id=device_id, user_id=user.id))
    row = inventory_row(session_factory, device_id)
    assert (row.status, row.holder_name, row.holder_department) == ("ASSIGNED", "Envanter Kul.", "Fizik")

    record_id = StartMaintenanceHandler(uow).handle(
        StartMaintenanceCommand(
            actor_id=tech.id, device_id=device_id, type=MaintenanceType.REPAIR, description="Fan"
        )
    )
    row = inventory_row(session_factory, device_id)
    assert (row.status, row.has_open_maintenance, row.maintenance_count) == ("IN_REPAIR", True, 1)
    assert row.holder_name == "Envanter Kul."  # bakımdayken zimmet sürer

    CompleteMaintenanceHandler(uow).handle(
        CompleteMaintenanceCommand(actor_id=tech.id, maintenance_record_id=record_id)
    )
    ReturnDeviceHandler(uow).handle(ReturnDeviceCommand(actor_id=admin.id, device_id=device_id))
    row = inventory_row(session_factory, device_id)
    assert (row.status, row.holder_name, row.has_open_maintenance) == ("IN_STOCK", None, False)
    assert row.last_maintenance_at is not None


# --- Sorgular ve handler'lar ---


def test_inventory_report_counts_and_filters(session_factory, setup):
    uow, admin, _, user = setup
    # Test, seed verisi bulunan gerçek veritabanında çalışır: sayılar öncesine göre karşılaştırılır
    with session_factory() as session:
        queries = SqlInventoryQueries(session)
        before = queries.list_devices()
        before_assigned_laptops = queries.list_devices(DeviceStatus.ASSIGNED, "Dizüstü")
    laptop = register(uow, admin, "INV-0001", "Dizüstü")
    register(uow, admin, "INV-0002", "Dizüstü")
    register(uow, admin, "INV-0003", "Yazıcı")
    AssignDeviceHandler(uow).handle(AssignDeviceCommand(actor_id=admin.id, device_id=laptop, user_id=user.id))

    with session_factory() as session:
        handler = GetInventoryReportHandler(SqlInventoryQueries(session), SqlUserQueries(session))
        report = handler.handle(GetInventoryReportQuery(actor_id=admin.id))
        only_assigned_laptops = handler.handle(
            GetInventoryReportQuery(actor_id=admin.id, status=DeviceStatus.ASSIGNED, device_type="Dizüstü")
        )

    assert report.total == len(before) + 3
    assert all(status in report.by_status for status in DeviceStatus)  # sıfırlar da var
    assert only_assigned_laptops.total == len(before_assigned_laptops) + 1
    assert {d.status for d in only_assigned_laptops.devices} == {DeviceStatus.ASSIGNED}
    assert {d.type for d in only_assigned_laptops.devices} == {"Dizüstü"}
    ours = next(d for d in only_assigned_laptops.devices if d.asset_tag == "INV-0001")
    assert ours.holder_name == "Envanter Kul."


def test_inventory_report_is_admin_only(session_factory, setup):
    _, _, tech, _ = setup
    with session_factory() as session:
        handler = GetInventoryReportHandler(SqlInventoryQueries(session), SqlUserQueries(session))
        with pytest.raises(PermissionDeniedError):
            handler.handle(GetInventoryReportQuery(actor_id=tech.id))


def test_maintenance_history_newest_first_with_technician_name(session_factory, setup):
    uow, admin, tech, user = setup
    device_id = register(uow, admin)
    for description in ("İlk bakım", "İkinci bakım"):
        record_id = StartMaintenanceHandler(uow).handle(
            StartMaintenanceCommand(
                actor_id=tech.id, device_id=device_id, type=MaintenanceType.PERIODIC, description=description
            )
        )
        CompleteMaintenanceHandler(uow).handle(
            CompleteMaintenanceCommand(actor_id=tech.id, maintenance_record_id=record_id)
        )

    with session_factory() as session:
        handler = GetMaintenanceHistoryHandler(SqlInventoryQueries(session), SqlUserQueries(session))
        history = handler.handle(GetMaintenanceHistoryQuery(actor_id=tech.id, device_id=device_id))
        with pytest.raises(PermissionDeniedError):
            handler.handle(GetMaintenanceHistoryQuery(actor_id=user.id, device_id=device_id))  # UC-17: teknisyen ve yönetici
        with pytest.raises(NotFoundError):
            handler.handle(GetMaintenanceHistoryQuery(actor_id=admin.id, device_id=999_999))

    assert [h.description for h in history] == ["İkinci bakım", "İlk bakım"]
    assert history[0].technician_name == "Envanter Tek."
    assert not history[0].is_open


# --- API ---


def test_inventory_endpoints(session_factory, setup):
    uow, admin, tech, user = setup
    device_id = register(uow, admin)
    AssignDeviceHandler(uow).handle(AssignDeviceCommand(actor_id=admin.id, device_id=device_id, user_id=user.id))

    app = create_app()

    def test_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = test_session
    client = TestClient(app)

    mine = client.get("/devices/mine", headers={"X-User-Id": str(user.id)})
    assert [d["asset_tag"] for d in mine.json()] == ["INV-0001"]

    report = client.get("/inventory/report?type=Dizüstü", headers={"X-User-Id": str(admin.id)})
    assert report.status_code == 200
    assert report.json()["by_status"]["ASSIGNED"] >= 1

    history = client.get(
        f"/devices/{device_id}/maintenance-records", headers={"X-User-Id": str(tech.id)}
    )
    assert (history.status_code, history.json()) == (200, [])
