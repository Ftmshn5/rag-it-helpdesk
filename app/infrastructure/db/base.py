"""Tüm SQLAlchemy modellerinin ortak tabanı."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# CQRS yazma tarafı: normalize tablolar bu şemada yaşar.
# Okuma tarafının read model'leri ileride ayrı "read" şemasında olacak.
WRITE_SCHEMA = "write"

# Kısıt adlarını öngörülebilir yapar; Alembic migration'larında
# kısıtları adıyla bulup değiştirebilmek için gereklidir.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(schema=WRITE_SCHEMA, naming_convention=NAMING_CONVENTION)
