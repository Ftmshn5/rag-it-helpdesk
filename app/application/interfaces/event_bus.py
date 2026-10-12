"""Event bus arayüzü (Observer deseni).

Olayı yayınlayan taraf (subject) kimin dinlediğini bilmez; dinleyiciler
(observer) yalnızca ilgilendikleri olay tipine abone olur. Böylece örneğin
"ticket durumu değişti" olayına yeni bir dinleyici (bildirim, read model,
istatistik) eklemek, olayı üreten command handler'ı değiştirmeyi gerektirmez.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TypeVar

from app.domain.events import DomainEvent

TEvent = TypeVar("TEvent", bound=DomainEvent)

EventHandler = Callable[[TEvent], None]


class EventBus(ABC):
    @abstractmethod
    def subscribe(self, event_type: type[TEvent], handler: EventHandler) -> None: ...

    @abstractmethod
    def publish(self, event: DomainEvent) -> None: ...
