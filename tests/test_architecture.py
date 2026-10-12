"""Mimari kural testi: domain katmanı dış katmanlara ve framework'lere bağımlı olmamalı.

Bu test, Clean Architecture'daki bağımlılık kuralını otomatik olarak denetler;
biri yanlışlıkla domain'e SQLAlchemy veya FastAPI import ederse test kırılır.
"""

import ast
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parent.parent / "app" / "domain"

FORBIDDEN_IMPORTS = (
    "sqlalchemy",
    "fastapi",
    "pydantic",
    "app.api",
    "app.application",
    "app.infrastructure",
    "app.core",
)


def imported_modules(file_path: Path) -> set[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


APPLICATION_DIR = DOMAIN_DIR.parent / "application"

# Application katmanı domain'i ve kendi arayüzlerini bilir; somut altyapıyı bilmez
APPLICATION_FORBIDDEN_IMPORTS = (
    "sqlalchemy",
    "fastapi",
    "pgvector",
    "app.api",
    "app.infrastructure",
)


def find_violations(directory: Path, forbidden: tuple[str, ...]) -> list[str]:
    violations = []
    for file_path in directory.rglob("*.py"):
        for module in imported_modules(file_path):
            if module.startswith(forbidden):
                violations.append(f"{file_path.name}: {module}")
    return violations


def test_domain_has_no_outer_layer_dependencies():
    assert find_violations(DOMAIN_DIR, FORBIDDEN_IMPORTS) == []


def test_application_does_not_depend_on_infrastructure():
    assert find_violations(APPLICATION_DIR, APPLICATION_FORBIDDEN_IMPORTS) == []
