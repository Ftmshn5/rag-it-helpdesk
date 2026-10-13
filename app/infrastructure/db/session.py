"""Veritabanı bağlantısı (engine) ve oturum (session) üretimi.

SQLAlchemy'ye özgü kod yalnızca infrastructure katmanında yaşar;
domain ve application katmanları bu modülü doğrudan import etmez.
"""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """Bir veritabanına bağlantı havuzu (engine) ve oturum fabrikası.

    Modül seviyesinde global engine yerine bu sınıfın tek bir nesnesi
    kompozisyon kökünde (core/dependencies.py: get_database) oluşturulur ve
    ihtiyaç duyan sınıflara oturum fabrikası (`session_factory`) olarak verilir.
    Testler aynı sınıfı kendi transaction'larına bağlı fabrikayla kullanır.
    """

    def __init__(self, url: str) -> None:
        self._engine = create_engine(
            url,
            # Havuzdan alınan bağlantı kopmuşsa kullanmadan önce fark et
            pool_pre_ping=True,
            # DB kapalıyken isteklerin uzun süre beklememesi için
            connect_args={"connect_timeout": 3},
        )
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, expire_on_commit=False)

    @property
    def engine(self) -> Engine:
        return self._engine

    @property
    def session_factory(self) -> sessionmaker[Session]:
        """Repository / Unit of Work / projektörlere verilen oturum fabrikası."""
        return self._session_factory

    def sessions(self) -> Iterator[Session]:
        """Her HTTP isteği için bir oturum açar, istek bitince kapatır (FastAPI bağımlılığı)."""
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def is_available(self) -> bool:
        """Basit bir sorgu atarak veritabanına erişilebilir olup olmadığını döndürür."""
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False
