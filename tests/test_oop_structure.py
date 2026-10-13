"""OOP kuralları testi: CQRS sınıflarının kalıtım ve adlandırma düzeni.

CLAUDE.md'deki "Sınıf tabanlı katmanlar" kuralını otomatik denetler: yeni
eklenen bir handler temel sınıftan türemezse veya command/query adı düzene
uymazsa test kırılır.
"""

import importlib
import inspect
import pkgutil
from types import ModuleType

import pytest

import app.application.commands as commands_package
import app.application.queries as queries_package
from app.application.commands.base import Command, CommandHandler
from app.application.queries.base import Query, QueryHandler


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


def test_handlers_have_no_module_level_helper_functions():
    """Ortak kontroller temel sınıfların korumalı metotlarıdır, modül fonksiyonu değil."""
    for module in modules_of(commands_package) + modules_of(queries_package):
        functions = [name for name, f in inspect.getmembers(module, inspect.isfunction) if f.__module__ == module.__name__]
        assert functions == [], f"{module.__name__}: {functions}"
