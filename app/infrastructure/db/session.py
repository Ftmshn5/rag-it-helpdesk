"""Veritabanı bağlantısı (engine) ve oturum (session) üretimi.

SQLAlchemy'ye özgü kod yalnızca infrastructure katmanında yaşar;
domain ve application katmanları bu modülü doğrudan import etmez.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(
    get_settings().database_url,
    # Havuzdan alınan bağlantı kopmuşsa kullanmadan önce fark et
    pool_pre_ping=True,
    # DB kapalıyken isteklerin uzun süre beklememesi için
    connect_args={"connect_timeout": 3},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Her HTTP isteği için bir oturum açar, istek bitince kapatır."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> bool:
    """Veritabanına basit bir sorgu atarak erişilebilir olup olmadığını döndürür."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
