"""Domain olayları (domain events).

Bir olay, sistemde "olmuş bir şeyi" geçmiş zamanla anlatır: DeviceAssigned,
TicketStatusChanged gibi. Olaylar değiştirilemez (frozen) — geçmiş değişmez.

Somut olaylar, onları üreten iş akışlarıyla birlikte sonraki adımlarda
(envanter, ticket) bu modüle eklenecek.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.clock import utc_now


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=utc_now)
