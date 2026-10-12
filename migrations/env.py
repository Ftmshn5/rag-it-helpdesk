"""Alembic çalışma ortamı.

Bağlantı adresi alembic.ini'den değil, uygulamayla aynı yerden (.env → Settings)
okunur; böylece adres tek bir yerde tanımlı kalır.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.infrastructure.db import models  # noqa: F401  (modelleri metadata'ya kaydeder)
from app.infrastructure.db.base import WRITE_SCHEMA, Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
database_url = get_settings().database_url

# Alembic'in yöneteceği şemalar; public gibi diğer şemalara dokunmaz
MANAGED_SCHEMAS = {WRITE_SCHEMA}


def include_name(name, type_, parent_names) -> bool:
    if type_ == "schema":
        return name in MANAGED_SCHEMAS
    return True


def configure_context(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    configure_context(
        url=database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        configure_context(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
