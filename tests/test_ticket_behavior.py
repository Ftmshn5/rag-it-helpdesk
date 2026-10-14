"""Decorator ve Factory testleri (saf domain, veritabanı yok)."""

import pytest

from app.domain.enums import TicketCategory, TicketModifier
from app.domain.notifications import NotificationAudience, NotificationChannel
from app.domain.ticket import Ticket
from app.domain.ticket_behavior import (
    BasicTicket,
    TicketComponentFactory,
    UrgentTicket,
    VipTicket,
)

VIP, URGENT = TicketModifier.VIP, TicketModifier.URGENT


def make_ticket(modifiers=()) -> Ticket:
    return Ticket(
        title="Yazıcı çalışmıyor",
        description="Kağıt sıkışıyor",
        category=TicketCategory.HARDWARE,
        requester_id=1,
        modifiers=list(modifiers),
    )


# --- Decorator: davranışlar zincirlenir ---


def test_basic_ticket_defaults():
    behavior = BasicTicket(make_ticket())

    assert behavior.sla_hours() == 72
    assert behavior.priority_score() == 10
    assert [n.channel for n in behavior.notify()] == [NotificationChannel.IN_APP]


def test_claude_md_example_sla_72_24_4():
    """CLAUDE.md örneği: UrgentTicket(VipTicket(BasicTicket(data))) → 72 → 24 → 4."""
    basic = BasicTicket(make_ticket())
    vip = VipTicket(basic)
    urgent_vip = UrgentTicket(vip)

    assert [basic.sla_hours(), vip.sla_hours(), urgent_vip.sla_hours()] == [72, 24, 4]


def test_priority_bonuses_are_added_by_each_layer():
    assert UrgentTicket(VipTicket(BasicTicket(make_ticket()))).priority_score() == 10 + 20 + 50


def test_notifications_are_chained_from_inner_to_outer():
    notifications = UrgentTicket(VipTicket(BasicTicket(make_ticket()))).notify()

    assert [(n.channel, n.audience) for n in notifications] == [
        (NotificationChannel.IN_APP, NotificationAudience.TECHNICIANS),
        (NotificationChannel.EMAIL, NotificationAudience.IT_MANAGERS),
        (NotificationChannel.SMS, NotificationAudience.ON_CALL_TECHNICIANS),
    ]
    assert notifications[-1].message == "ACİL talep: Yazıcı çalışmıyor"


def test_wrapping_order_does_not_change_sla():
    """SLA'lar üst sınır (min) olduğu için sarma sırası sonucu değiştirmez."""
    ticket = make_ticket()
    assert UrgentTicket(VipTicket(BasicTicket(ticket))).sla_hours() == 4
    assert VipTicket(UrgentTicket(BasicTicket(ticket))).sla_hours() == 4


def test_decorators_expose_the_same_underlying_ticket():
    ticket = make_ticket()
    assert UrgentTicket(VipTicket(BasicTicket(ticket))).ticket is ticket


# --- Factory: modifiers listesinden nesne üretir ---


@pytest.mark.parametrize(
    "modifiers, expected_type, sla, score",
    [
        ([], BasicTicket, 72, 10),
        ([VIP], VipTicket, 24, 30),
        ([URGENT], UrgentTicket, 4, 60),
        ([VIP, URGENT], UrgentTicket, 4, 80),
        ([URGENT, VIP], UrgentTicket, 4, 80),  # liste sırası önemli değil
    ],
)
def test_factory_wraps_ticket_according_to_modifiers(modifiers, expected_type, sla, score):
    behavior = TicketComponentFactory.create(make_ticket(modifiers))

    assert type(behavior) is expected_type
    assert behavior.sla_hours() == sla
    assert behavior.priority_score() == score


def test_factory_applies_decorators_in_canonical_order():
    """Liste sırasından bağımsız olarak VIP içte, Acil dışta: bildirim sırası hep aynı."""
    behavior = TicketComponentFactory.create(make_ticket([URGENT, VIP]))

    assert [n.audience for n in behavior.notify()] == [
        NotificationAudience.TECHNICIANS,
        NotificationAudience.IT_MANAGERS,
        NotificationAudience.ON_CALL_TECHNICIANS,
    ]
