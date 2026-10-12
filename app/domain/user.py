from dataclasses import dataclass

from app.domain.enums import UserRole


@dataclass(kw_only=True)
class User:
    id: int | None = None
    full_name: str
    email: str
    role: UserRole = UserRole.USER
    department: str | None = None
    is_vip: bool = False

    @property
    def is_technician(self) -> bool:
        return self.role == UserRole.TECHNICIAN
