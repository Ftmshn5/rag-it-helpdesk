"""Bildirim testleri: Observer (olay → bildirim), Strategy (kanal göndericileri),
Decorator (talep açılınca kime) ve State (durum değişince kime).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.application.commands.notifications import (
    MarkNotificationsReadCommand,
    MarkNotificationsReadHandler,
    NotifyTicketCreatedCommand,
    NotifyTicketCreatedHandler,
    NotifyTicketStatusChangedCommand,
    NotifyTicketStatusChangedHandler,
)
from app.application.errors import AuthenticationError, NotFoundError
from app.application.event_handlers import TicketCreatedNotifier, TicketStatusNotifier
from app.application.interfaces.notification_sender import NotificationSender
from app.application.queries.notifications import (
    GetMyNotificationsHandler,
    GetMyNotificationsQuery,
    NotificationQueries,
    NotificationView,
)
from app.application.queries.users import UserQueries, UserView
from app.core.dependencies import get_db_session, get_unit_of_work
from app.core.event_subscriptions import EventSubscriptions
from app.domain.enums import SupportLevel, TicketCategory, TicketModifier, TicketStatus, UserRole
from app.domain.events import TicketCreated, TicketStatusChanged
from app.domain.notifications import NotificationAudience, NotificationChannel, UserNotification
from app.domain.ticket import Ticket
from app.domain.ticket_state import STATES
from app.domain.user import User
from app.infrastructure.db.queries import SqlNotificationQueries
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from app.main import create_app
from tests.fakes import FakeEventBus, FakeUnitOfWork

S = TicketStatus
C = NotificationChannel


class RecordingSender(NotificationSender):
    """Test göndericisi: teslim edilenleri listede biriktirir (Strategy'nin sahte hali)."""

    def __init__(self, channel: NotificationChannel, uow: FakeUnitOfWork) -> None:
        self.channel = channel
        self._uow = uow
        self.delivered: list[tuple[int, str]] = []
        self.committed_before_delivery: list[bool] = []

    def deliver(self, recipient: User, notification: UserNotification) -> None:
        self.delivered.append((recipient.id, notification.message))
        self.committed_before_delivery.append(self._uow.committed)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.users.add(User(full_name="Dekan", email="dekan@x.edu", is_vip=True))  # 1
    uow.users.add(User(full_name="Ali", email="ali@x.edu", role=UserRole.TECHNICIAN))  # 2
    uow.users.add(
        User(full_name="Elif", email="elif@x.edu", role=UserRole.TECHNICIAN, support_level=SupportLevel.TIER_2)
    )  # 3
    uow.users.add(User(full_name="Can", email="can@x.edu", role=UserRole.ADMIN))  # 4
    return uow


REQUESTER, TECH, SENIOR, ADMIN = 1, 2, 3, 4


@pytest.fixture
def senders(uow) -> dict[NotificationChannel, RecordingSender]:
    return {channel: RecordingSender(channel, uow) for channel in NotificationChannel}


def add_ticket(uow, *, modifiers=(), status=S.OPEN, assignee_id=None) -> int:
    ticket = Ticket(
        title="Yazıcı çalışmıyor",
        description="-",
        category=TicketCategory.HARDWARE,
        requester_id=REQUESTER,
        status=status,
        assignee_id=assignee_id,
        modifiers=list(modifiers),
        support_level=SupportLevel.AI if status == S.OPEN else SupportLevel.TIER_1,
    )
    return uow.tickets.add(ticket).id


def stored(uow) -> set[tuple[int, NotificationChannel]]:
    return {(n.recipient_id, n.channel) for n in uow.notifications.items.values()}


# --- Domain ---


def test_user_notification_is_created_from_a_description_and_marked_read_once():
    notification = UserNotification.deliver(
        STATES[S.ASSIGNED].entry_notifications("t")[0], recipient_id=5, ticket_id=9
    )
    assert (notification.recipient_id, notification.ticket_id, notification.is_read) == (5, 9, False)

    notification.mark_read()
    first_read = notification.read_at
    notification.mark_read()

    assert notification.is_read and notification.read_at == first_read
    assert notification.belongs_to(5) and not notification.belongs_to(6)


@pytest.mark.parametrize(
    ("status", "audiences"),
    [
        (S.OPEN, []),
        (S.AI_ANSWERED, [NotificationAudience.REQUESTER]),
        (S.ESCALATED, [NotificationAudience.IT_MANAGERS]),
        (S.ASSIGNED, [NotificationAudience.ASSIGNEE, NotificationAudience.REQUESTER]),
        (S.IN_PROGRESS, [NotificationAudience.REQUESTER]),
        (S.RESOLVED, [NotificationAudience.REQUESTER]),
        (S.CLOSED, []),
    ],
)
def test_each_state_knows_whom_to_notify_on_entry(status, audiences):
    """State: hangi durumda kime haber verileceği if/elif ile değil, durum nesnesiyle belirlenir."""
    assert [n.audience for n in STATES[status].entry_notifications("t")] == audiences


# --- Talep açıldı: Decorator zinciri ---


def test_basic_ticket_notifies_all_technicians_in_app(uow, senders):
    ticket_id = add_ticket(uow)

    count = NotifyTicketCreatedHandler(uow, senders.values()).handle(
        NotifyTicketCreatedCommand(ticket_id=ticket_id, actor_id=REQUESTER)
    )

    assert count == 2
    assert stored(uow) == {(TECH, C.IN_APP), (SENIOR, C.IN_APP)}
    assert uow.committed


def test_vip_urgent_ticket_adds_email_to_managers_and_sms_to_on_call(uow, senders):
    ticket_id = add_ticket(uow, modifiers=[TicketModifier.VIP, TicketModifier.URGENT])

    NotifyTicketCreatedHandler(uow, senders.values()).handle(NotifyTicketCreatedCommand(ticket_id=ticket_id))

    assert stored(uow) == {
        (TECH, C.IN_APP),
        (SENIOR, C.IN_APP),
        (ADMIN, C.EMAIL),  # VipTicket
        (SENIOR, C.SMS),  # UrgentTicket: nöbetçi = kıdemli teknisyen
    }
    # Strategy: her bildirim kendi kanalının göndericisine gider
    assert [recipient for recipient, _ in senders[C.EMAIL].delivered] == [ADMIN]
    assert senders[C.SMS].delivered == [(SENIOR, "ACİL talep: Yazıcı çalışmıyor")]


def test_delivery_happens_only_after_commit(uow, senders):
    ticket_id = add_ticket(uow)
    NotifyTicketCreatedHandler(uow, senders.values()).handle(NotifyTicketCreatedCommand(ticket_id=ticket_id))
    assert senders[C.IN_APP].committed_before_delivery == [True, True]


def test_missing_ticket_produces_no_notifications(uow, senders):
    assert NotifyTicketCreatedHandler(uow, senders.values()).handle(NotifyTicketCreatedCommand(ticket_id=99)) == 0
    assert stored(uow) == set()


# --- Durum değişti: State ---


def test_assignment_notifies_technician_and_requester_but_not_the_admin_who_did_it(uow, senders):
    ticket_id = add_ticket(uow, status=S.ASSIGNED, assignee_id=TECH)

    NotifyTicketStatusChangedHandler(uow, senders.values()).handle(
        NotifyTicketStatusChangedCommand(ticket_id=ticket_id, actor_id=ADMIN, new_status=S.ASSIGNED)
    )

    assert stored(uow) == {(TECH, C.IN_APP), (REQUESTER, C.IN_APP)}


def test_actor_does_not_notify_themselves(uow, senders):
    """Teknisyen talebi çözdü → yalnızca talep sahibi haber alır."""
    ticket_id = add_ticket(uow, status=S.RESOLVED, assignee_id=TECH)

    NotifyTicketStatusChangedHandler(uow, senders.values()).handle(
        NotifyTicketStatusChangedCommand(ticket_id=ticket_id, actor_id=TECH, new_status=S.RESOLVED)
    )

    assert stored(uow) == {(REQUESTER, C.IN_APP)}


def test_escalation_notifies_it_managers(uow, senders):
    ticket_id = add_ticket(uow, status=S.ESCALATED)

    NotifyTicketStatusChangedHandler(uow, senders.values()).handle(
        NotifyTicketStatusChangedCommand(ticket_id=ticket_id, actor_id=None, new_status=S.ESCALATED)
    )

    assert stored(uow) == {(ADMIN, C.IN_APP)}


# --- Observer: olay → bildirim ---


def test_notifiers_are_subscribed_to_their_events_and_build_commands():
    received = []

    class FakeHandler:
        def handle(self, command) -> None:
            received.append(command)

    bus = InMemoryEventBus()
    EventSubscriptions(
        auto_answer=None,  # TicketCreated'a abone olur ama bu testte olay yayınlanmaz
        notifiers=(TicketCreatedNotifier(FakeHandler), TicketStatusNotifier(FakeHandler)),
    ).register(bus)

    bus.publish(
        TicketStatusChanged(ticket_id=7, old_status=S.ESCALATED, new_status=S.ASSIGNED, actor_id=ADMIN, assignee_id=2)
    )

    assert received == [NotifyTicketStatusChangedCommand(ticket_id=7, actor_id=ADMIN, new_status=S.ASSIGNED)]
    assert TicketCreatedNotifier(FakeHandler).command_for(
        TicketCreated(ticket_id=7, requester_id=REQUESTER, sla_hours=72, priority_score=10)
    ) == NotifyTicketCreatedCommand(ticket_id=7, actor_id=REQUESTER)


# --- Okundu işaretleme ---


def add_notification(uow, recipient_id: int) -> int:
    return uow.notifications.add(
        UserNotification(recipient_id=recipient_id, ticket_id=None, channel=C.IN_APP, message="m")
    ).id


def test_mark_all_unread_notifications_as_read(uow):
    mine = [add_notification(uow, REQUESTER), add_notification(uow, REQUESTER)]
    others = add_notification(uow, TECH)

    MarkNotificationsReadHandler(uow).handle(MarkNotificationsReadCommand(actor_id=REQUESTER))

    assert all(uow.notifications.get(n).is_read for n in mine)
    assert not uow.notifications.get(others).is_read


def test_mark_selected_notification_as_read(uow):
    first, second = add_notification(uow, REQUESTER), add_notification(uow, REQUESTER)

    MarkNotificationsReadHandler(uow).handle(MarkNotificationsReadCommand(actor_id=REQUESTER, notification_ids=(first,)))

    assert uow.notifications.get(first).is_read
    assert not uow.notifications.get(second).is_read


def test_cannot_mark_someone_elses_notification(uow):
    others = add_notification(uow, TECH)
    with pytest.raises(NotFoundError):
        MarkNotificationsReadHandler(uow).handle(
            MarkNotificationsReadCommand(actor_id=REQUESTER, notification_ids=(others,))
        )
    assert not uow.notifications.get(others).is_read


# --- Veritabanı: repository + okuma sorgusu ---


def test_sql_repository_and_queries(sqlalchemy_uow, session_factory):
    with sqlalchemy_uow:
        user = sqlalchemy_uow.users.add(User(full_name="Bildirim Test", email="bildirim.test@x.edu"))
        technician = sqlalchemy_uow.users.add(
            User(full_name="Kıdemli Test", email="kidemli.test@x.edu", role=UserRole.TECHNICIAN,
                 support_level=SupportLevel.TIER_2)
        )
        old = sqlalchemy_uow.notifications.add(
            UserNotification(recipient_id=user.id, ticket_id=None, channel=C.EMAIL, message="eski")
        )
        sqlalchemy_uow.notifications.add(
            UserNotification(recipient_id=user.id, ticket_id=None, channel=C.IN_APP, message="yeni")
        )
        sqlalchemy_uow.commit()

    with sqlalchemy_uow:
        assert technician.id in {u.id for u in sqlalchemy_uow.users.list_by_role(UserRole.TECHNICIAN)}
        assert sqlalchemy_uow.users.get(technician.id).support_level == SupportLevel.TIER_2
        notification = sqlalchemy_uow.notifications.get(old.id)
        notification.mark_read()
        sqlalchemy_uow.notifications.update(notification)
        sqlalchemy_uow.commit()

    with sqlalchemy_uow:
        assert [n.message for n in sqlalchemy_uow.notifications.list_unread_for(user.id)] == ["yeni"]

    session: Session = session_factory()
    queries = SqlNotificationQueries(session)
    assert queries.unread_count(user.id) == 1
    items = queries.recent_for(user.id, limit=10)
    assert [(n.message, n.channel, n.is_read) for n in items] == [("yeni", C.IN_APP, False), ("eski", C.EMAIL, True)]
    session.close()


# --- Okuma: zil menüsü sorgusu ---


class FakeNotificationQueries(NotificationQueries):
    def __init__(self) -> None:
        self.requested: list[tuple[int, int]] = []

    def recent_for(self, user_id: int, limit: int) -> list[NotificationView]:
        self.requested.append((user_id, limit))
        return []

    def unread_count(self, user_id: int) -> int:
        return 3


class FakeUserQueries(UserQueries):
    def get(self, user_id: int) -> UserView | None:
        return UserView(user_id, "Ayşe", "a@x.edu", UserRole.USER, None, False, None) if user_id == 1 else None

    def list_all(self) -> list[UserView]:
        return []


@pytest.mark.parametrize(("limit", "expected"), [(20, 20), (0, 1), (500, GetMyNotificationsHandler.MAX_LIMIT)])
def test_my_notifications_are_read_for_the_viewer_with_a_bounded_limit(limit, expected):
    notifications = FakeNotificationQueries()

    view = GetMyNotificationsHandler(notifications, FakeUserQueries()).handle(
        GetMyNotificationsQuery(actor_id=1, limit=limit)
    )

    assert view.unread_count == 3
    assert notifications.requested == [(1, expected)]


def test_unknown_viewer_cannot_read_notifications():
    with pytest.raises(AuthenticationError):
        GetMyNotificationsHandler(FakeNotificationQueries(), FakeUserQueries()).handle(GetMyNotificationsQuery(actor_id=99))


# --- API ---


def test_notification_endpoints(session_factory):
    uow = SqlAlchemyUnitOfWork(FakeEventBus(), session_factory)
    with uow:
        user = uow.users.add(User(full_name="Zil Test", email="zil.test@x.edu"))
        other = uow.users.add(User(full_name="Zil Başka", email="zil.baska@x.edu"))
        first = uow.notifications.add(
            UserNotification(recipient_id=user.id, ticket_id=None, channel=C.IN_APP, message="bir")
        )
        uow.notifications.add(UserNotification(recipient_id=user.id, ticket_id=None, channel=C.SMS, message="iki"))
        foreign = uow.notifications.add(
            UserNotification(recipient_id=other.id, ticket_id=None, channel=C.IN_APP, message="başkası")
        )
        uow.commit()

    app = create_app()

    def test_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = test_session
    app.dependency_overrides[get_unit_of_work] = lambda: SqlAlchemyUnitOfWork(FakeEventBus(), session_factory)
    client = TestClient(app)
    headers = {"X-User-Id": str(user.id)}

    body = client.get("/notifications/mine", headers=headers).json()
    assert body["unread_count"] == 2
    assert [item["message"] for item in body["items"]] == ["iki", "bir"]  # en yeni önce

    assert client.post("/notifications/read", json={"notification_ids": [first.id]}, headers=headers).status_code == 204
    assert client.get("/notifications/mine", headers=headers).json()["unread_count"] == 1

    # Başkasının bildirimi: 404 (varlığı sızdırılmaz)
    response = client.post("/notifications/read", json={"notification_ids": [foreign.id]}, headers=headers)
    assert response.status_code == 404

    assert client.post("/notifications/read", json={}, headers=headers).status_code == 204
    assert client.get("/notifications/mine", headers=headers).json()["unread_count"] == 0
    assert client.get("/notifications/mine?limit=0", headers=headers).status_code == 422
