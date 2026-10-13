"""Event bus arayüzü (Observer deseni).

Olayı yayınlayan taraf (subject) kimin dinlediğini bilmez; dinleyiciler
(observer) yalnızca ilgilendikleri olay tipine abone olur. Böylece örneğin
"ticket durumu değişti" olayına yeni bir dinleyici (bildirim, read model,
istatistik) eklemek, olayı üreten command handler'ı değiştirmeyi gerektirmez.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.domain.events import DomainEvent

TEvent = TypeVar("TEvent", bound=DomainEvent)


class EventHandler(ABC, Generic[TEvent]):
    """Observer deseni — Observer: abone olduğu olay tipini işler.

    Somut dinleyiciler: EventLogger (tüm olayları loglar), AutoAnswerScheduler
    (yeni talepte AI'ı tetikler), Projector'lar (read model'leri günceller).
    """

    @abstractmethod
    def handle(self, event: TEvent) -> None: ...


class EventBus(ABC):
    """Observer deseni — Subject: olayları abonelere iletir."""

    @abstractmethod
    def subscribe(self, event_type: type[TEvent], handler: EventHandler[TEvent]) -> None: ...

    @abstractmethod
    def publish(self, event: DomainEvent) -> None: ...
