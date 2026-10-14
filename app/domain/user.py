"""Kullanıcı varlığı. Kullanıcılar seed data ile gelir; uygulama içinde değişmez."""

from app.domain.entity import Entity
from app.domain.enums import SupportLevel, UserRole


class User(Entity):
    """Sistemi kullanan kişi (kullanıcı, teknisyen veya BT yöneticisi). Salt okunur."""

    def __init__(
        self,
        *,
        id: int | None = None,
        full_name: str,
        email: str,
        role: UserRole = UserRole.USER,
        department: str | None = None,
        is_vip: bool = False,
        support_level: SupportLevel | None = None,
    ) -> None:
        super().__init__(id)
        self._full_name = full_name
        self._email = email
        self._role = role
        self._department = department
        self._is_vip = is_vip
        # Destek seviyesi yalnızca teknisyenler için anlamlıdır; belirtilmezse L1
        self._support_level = (support_level or SupportLevel.TIER_1) if role == UserRole.TECHNICIAN else None

    @property
    def full_name(self) -> str:
        return self._full_name

    @property
    def email(self) -> str:
        return self._email

    @property
    def role(self) -> UserRole:
        return self._role

    @property
    def department(self) -> str | None:
        return self._department

    @property
    def is_vip(self) -> bool:
        return self._is_vip

    @property
    def support_level(self) -> SupportLevel | None:
        """Teknisyenin bakabildiği en üst destek seviyesi; teknisyen değilse None."""
        return self._support_level

    @property
    def is_technician(self) -> bool:
        return self._role == UserRole.TECHNICIAN

    @property
    def is_admin(self) -> bool:
        return self._role == UserRole.ADMIN
