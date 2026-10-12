"""Domain'deki sabit değer kümeleri.

StrEnum kullanıldı: değerler düz metin olduğu için veritabanına ve JSON'a
dönüştürme ek kod gerektirmez (örn. TicketStatus.OPEN == "OPEN").
"""

from enum import StrEnum


class UserRole(StrEnum):
    USER = "USER"
    TECHNICIAN = "TECHNICIAN"
    ADMIN = "ADMIN"


class DeviceStatus(StrEnum):
    IN_STOCK = "IN_STOCK"
    ASSIGNED = "ASSIGNED"
    IN_REPAIR = "IN_REPAIR"
    RETIRED = "RETIRED"


class MaintenanceType(StrEnum):
    REPAIR = "REPAIR"
    PERIODIC = "PERIODIC"
    PART_REPLACEMENT = "PART_REPLACEMENT"


class TicketCategory(StrEnum):
    HARDWARE = "HARDWARE"
    SOFTWARE = "SOFTWARE"
    NETWORK = "NETWORK"
    ACCOUNT = "ACCOUNT"


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    AI_ANSWERED = "AI_ANSWERED"
    ESCALATED = "ESCALATED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketModifier(StrEnum):
    """Ticket'ı saracak decorator'ları belirler; veritabanında liste olarak saklanır."""

    VIP = "VIP"
    URGENT = "URGENT"


class AiFeedback(StrEnum):
    HELPFUL = "HELPFUL"
    NOT_HELPFUL = "NOT_HELPFUL"
