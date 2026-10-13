from dataclasses import dataclass

import pytest

from app.domain.events import DomainEvent
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from tests.fakes import CallbackHandler, FakeUnitOfWork


@dataclass(frozen=True, kw_only=True)
class SomethingHappened(DomainEvent):
    value: int


@dataclass(frozen=True, kw_only=True)
class SomethingElseHappened(DomainEvent):
    pass


# --- InMemoryEventBus ---


def test_subscribers_receive_published_event_in_order():
    bus = InMemoryEventBus()
    calls = []
    bus.subscribe(SomethingHappened, CallbackHandler(lambda e: calls.append(("first", e.value))))
    bus.subscribe(SomethingHappened, CallbackHandler(lambda e: calls.append(("second", e.value))))

    bus.publish(SomethingHappened(value=42))

    assert calls == [("first", 42), ("second", 42)]


def test_subscriber_does_not_receive_other_event_types():
    bus = InMemoryEventBus()
    calls = []
    bus.subscribe(SomethingHappened, CallbackHandler(calls.append))

    bus.publish(SomethingElseHappened())

    assert calls == []


def test_base_class_subscriber_receives_all_events():
    bus = InMemoryEventBus()
    calls = []
    bus.subscribe(DomainEvent, CallbackHandler(lambda e: calls.append(type(e).__name__)))

    bus.publish(SomethingHappened(value=1))
    bus.publish(SomethingElseHappened())

    assert calls == ["SomethingHappened", "SomethingElseHappened"]


def test_general_subscribers_run_before_specific_ones():
    """Loglama gibi genel dinleyiciler, olayın yol açtığı iç içe olaylardan önce görür."""
    bus = InMemoryEventBus()
    calls = []

    def react(event):
        calls.append("özel")
        bus.publish(SomethingElseHappened())  # iç içe olay

    bus.subscribe(SomethingHappened, CallbackHandler(react))
    bus.subscribe(DomainEvent, CallbackHandler(lambda e: calls.append(f"log:{type(e).__name__}")))

    bus.publish(SomethingHappened(value=1))

    assert calls == ["log:SomethingHappened", "özel", "log:SomethingElseHappened"]


def test_failing_subscriber_does_not_stop_others(caplog):
    bus = InMemoryEventBus()
    calls = []

    def broken(_event):
        raise ValueError("bozuk dinleyici")

    bus.subscribe(SomethingHappened, CallbackHandler(broken))
    bus.subscribe(SomethingHappened, CallbackHandler(lambda e: calls.append(e.value)))

    bus.publish(SomethingHappened(value=7))

    assert calls == [7]
    assert "bozuk dinleyici" in caplog.text


# --- Unit of Work + olaylar ---


def test_events_are_published_only_after_commit():
    bus = InMemoryEventBus()
    uow = FakeUnitOfWork(bus)
    committed_at_publish_time = []
    bus.subscribe(SomethingHappened, CallbackHandler(lambda e: committed_at_publish_time.append(uow.committed)))

    with uow:
        uow.add_event(SomethingHappened(value=1))
        assert committed_at_publish_time == []  # henüz yayınlanmadı
        uow.commit()

    # Dinleyici çağrıldığında transaction zaten commit edilmişti
    assert committed_at_publish_time == [True]


def test_events_are_discarded_without_commit(uow, event_bus):
    with uow:
        uow.add_event(SomethingHappened(value=1))

    assert event_bus.published == []


def test_events_are_discarded_on_exception(uow, event_bus):
    with pytest.raises(RuntimeError):
        with uow:
            uow.add_event(SomethingHappened(value=1))
            raise RuntimeError("iş kuralı ihlali")

    assert event_bus.published == []


def test_discarded_events_do_not_leak_into_next_commit(uow, event_bus):
    with uow:
        uow.add_event(SomethingHappened(value=1))  # commit yok → atılmalı

    with uow:
        uow.add_event(SomethingHappened(value=2))
        uow.commit()

    assert [e.value for e in event_bus.published] == [2]
