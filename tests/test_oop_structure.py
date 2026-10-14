"""OOP kuralları testi: CQRS sınıflarının kalıtım ve adlandırma düzeni.

CLAUDE.md'deki "Sınıf tabanlı katmanlar" kuralını otomatik denetler: yeni
eklenen bir handler temel sınıftan türemezse veya command/query adı düzene
uymazsa test kırılır.
"""

import ast
import dataclasses
import importlib
import inspect
import pkgutil
from pathlib import Path
from types import ModuleType

import pytest

import app.application.commands as commands_package
import app.application.queries as queries_package
from app.application.commands.base import Command, CommandHandler
from app.application.queries.base import Query, QueryHandler
from app.domain.entity import Entity
from app.domain.enums import DeviceStatus, MaintenanceType, TicketCategory
from app.domain.inventory import Assignment, Device, MaintenanceRecord
from app.domain.knowledge import KnowledgeChunk, KnowledgeDocument
from app.domain.notifications import NotificationChannel, UserNotification
from app.domain.ticket import AIResponse, Ticket, TicketAttachment, TicketComment
from app.domain.user import User


def modules_of(package: ModuleType) -> list[ModuleType]:
    return [importlib.import_module(f"{package.__name__}.{info.name}") for info in pkgutil.iter_modules(package.__path__)]


def classes_defined_in(package: ModuleType) -> list[type]:
    found = []
    for module in modules_of(package):
        found += [c for _, c in inspect.getmembers(module, inspect.isclass) if c.__module__ == module.__name__]
    return found


COMMAND_CLASSES = classes_defined_in(commands_package)
QUERY_CLASSES = classes_defined_in(queries_package)


@pytest.mark.parametrize("cls", [c for c in COMMAND_CLASSES if c.__name__.endswith("Handler")], ids=lambda c: c.__name__)
def test_every_command_handler_derives_from_command_handler(cls):
    assert issubclass(cls, CommandHandler)


@pytest.mark.parametrize("cls", [c for c in QUERY_CLASSES if c.__name__.endswith("Handler")], ids=lambda c: c.__name__)
def test_every_query_handler_derives_from_query_handler(cls):
    assert issubclass(cls, QueryHandler)


@pytest.mark.parametrize("cls", [c for c in COMMAND_CLASSES if issubclass(c, Command)], ids=lambda c: c.__name__)
def test_command_names_end_with_command(cls):
    assert cls.__name__.endswith("Command")


@pytest.mark.parametrize("cls", [c for c in QUERY_CLASSES if issubclass(c, Query)], ids=lambda c: c.__name__)
def test_query_names_end_with_query(cls):
    assert cls.__name__.endswith("Query")


def test_commands_and_queries_are_immutable():
    """Command/query bir isteğin verisidir; handler'a verildikten sonra değişmemeli."""
    data_classes = [c for c in COMMAND_CLASSES if issubclass(c, Command)] + [
        c for c in QUERY_CLASSES if issubclass(c, Query)
    ]
    assert data_classes
    assert all(c.__dataclass_params__.frozen for c in data_classes)


ENTITY_SAMPLES = [
    User(full_name="A", email="a@x.edu"),
    Device(asset_tag="PC-1", type="PC", brand="B", model="M", serial_number="S"),
    Assignment(device_id=1, user_id=2, assigned_by=3),
    MaintenanceRecord(
        device_id=1, technician_id=2, type=MaintenanceType.REPAIR, description="-", previous_device_status=DeviceStatus.IN_STOCK
    ),
    Ticket(title="t", description="d", category=TicketCategory.HARDWARE, requester_id=1),
    TicketAttachment(ticket_id=1, file_path="f.png", mime_type="image/png"),
    TicketComment(ticket_id=1, author_id=1, content="not"),
    AIResponse(ticket_id=1, answer="a", confidence=0.9),
    KnowledgeDocument(title="t", file_path="knowledge/t.md"),
    KnowledgeChunk(document_id=1, content="c"),
    UserNotification(recipient_id=1, ticket_id=None, channel=NotificationChannel.IN_APP, message="m"),
]


@pytest.mark.parametrize("entity", ENTITY_SAMPLES, ids=lambda e: type(e).__name__)
def test_domain_entities_are_encapsulated(entity):
    """Kapsülleme: varlıklar Entity'den türer, dataclass değildir, tüm alanları korumalıdır
    ve hiçbir özelliğin setter'ı yoktur (durum yalnızca iş metotlarıyla değişir)."""
    cls = type(entity)
    assert isinstance(entity, Entity)
    assert not dataclasses.is_dataclass(cls)
    assert all(name.startswith("_") for name in vars(entity)), vars(entity).keys()
    properties = {name: attr for klass in cls.__mro__ for name, attr in vars(klass).items() if isinstance(attr, property)}
    assert properties, "okuma özellikleri olmalı"
    assert all(prop.fset is None for prop in properties.values())


APP_DIR = Path(__file__).resolve().parents[1] / "app"
# Çerçevenin giriş noktaları bilinçli olarak fonksiyondur (iş mantığı içermezler):
# FastAPI router'ları ve Depends sağlayıcıları, uygulama fabrikası, CLI main()'leri.
FRAMEWORK_ENTRY_POINTS = ("api/", "core/", "main.py")
CLI_ENTRY_POINT = "main"


def test_no_module_level_functions_outside_framework_entry_points():
    """'Global değişken ve modül seviyesinde iş mantığı yok' kuralı: yardımcılar sınıflardadır."""
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        relative = path.relative_to(APP_DIR).as_posix()
        if relative.startswith(FRAMEWORK_ENTRY_POINTS):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders += [
            f"{relative}: {node.name}"
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name != CLI_ENTRY_POINT
        ]
    assert offenders == []


def test_handlers_have_no_module_level_helper_functions():
    """Ortak kontroller temel sınıfların korumalı metotlarıdır, modül fonksiyonu değil."""
    for module in modules_of(commands_package) + modules_of(queries_package):
        functions = [name for name, f in inspect.getmembers(module, inspect.isfunction) if f.__module__ == module.__name__]
        assert functions == [], f"{module.__name__}: {functions}"
