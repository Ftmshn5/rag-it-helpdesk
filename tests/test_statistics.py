"""UC-12 arıza istatistikleri: handler (yetki), SQL toplama sorguları (gerçek PostgreSQL) ve endpoint.

SQL testinde read model'e değerleri bilinen 5 satır eklenir; her göstergenin
beklenen değeri aşağıdaki tablodan elle hesaplanabilir (eşik 0.6, "şimdi" =
2026-10-14 Çarşamba 12:00 UTC, bu haftanın pazartesisi 2026-10-12):

  #  kategori  durum      açılış        çözülme       son tarih    AI güven  geri bildirim
  1  HARDWARE  CLOSED     10-13 10:00   10-13 14:00   10-16        0.9       HELPFUL
  2  NETWORK   RESOLVED   10-06 09:00   10-09 09:00   10-07 09:00  0.3       -
  3  SOFTWARE  ASSIGNED   10-01 08:00   -             10-02        -         -
  4  HARDWARE  OPEN       10-14 11:00   -             10-17        -         -
  5  ACCOUNT   ESCALATED  09-20 10:00   -             10-30        0.8       NOT_HELPFUL
"""

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.application.errors import PermissionDeniedError
from app.application.queries.statistics import (
    FailureStatisticsView,
    GetFailureStatisticsHandler,
    GetFailureStatisticsQuery,
    StatisticsQueries,
    WeeklyCountView,
)
from app.application.queries.users import UserQueries, UserView
from app.core.dependencies import get_db_session
from app.domain.enums import SupportLevel, TicketCategory, TicketStatus, UserRole
from app.infrastructure.db.read_models import TicketSummaryModel
from app.infrastructure.db.statistics import SqlStatisticsQueries
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import create_app
from tests.fakes import FakeEventBus

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
THRESHOLD = 0.6


def at(month: int, day: int, hour: int = 0) -> datetime:
    return datetime(2026, month, day, hour, 0, tzinfo=UTC)


def summary_row(ticket_id: int, category: TicketCategory, status: TicketStatus, created: datetime, due: datetime,
                resolved: datetime | None = None, confidence: float | None = None,
                feedback: str | None = None) -> TicketSummaryModel:
    return TicketSummaryModel(
        ticket_id=ticket_id, title=f"t{ticket_id}", category=category.value, status=status.value, support_level=SupportLevel.TIER_1.value,
        requester_id=1, requester_name="A", is_vip=False, is_urgent=False, sla_hours=72, priority_score=10,
        due_at=due, ai_confidence=confidence, ai_feedback=feedback, comment_count=0, attachment_count=0,
        created_at=created, resolved_at=resolved, refreshed_at=NOW,
    )


@pytest.fixture
def statistics(session_factory) -> FailureStatisticsView:
    with session_factory() as session, session.begin():
        # Geliştirme veritabanındaki gerçek talepler testi etkilemesin (test sonunda geri alınır)
        session.execute(delete(TicketSummaryModel))
        session.add_all([
            summary_row(1, TicketCategory.HARDWARE, TicketStatus.CLOSED, at(10, 13, 10), at(10, 16),
                        resolved=at(10, 13, 14), confidence=0.9, feedback="HELPFUL"),
            summary_row(2, TicketCategory.NETWORK, TicketStatus.RESOLVED, at(10, 6, 9), at(10, 7, 9),
                        resolved=at(10, 9, 9), confidence=0.3),
            summary_row(3, TicketCategory.SOFTWARE, TicketStatus.ASSIGNED, at(10, 1, 8), at(10, 2)),
            summary_row(4, TicketCategory.HARDWARE, TicketStatus.OPEN, at(10, 14, 11), at(10, 17)),
            summary_row(5, TicketCategory.ACCOUNT, TicketStatus.ESCALATED, at(9, 20, 10), at(10, 30),
                        confidence=0.8, feedback="NOT_HELPFUL"),
        ])
    with session_factory() as session:
        return SqlStatisticsQueries(session).failure_statistics(ai_threshold=THRESHOLD, weeks=3, now=NOW)


# --- SQL toplama sorguları ---


def test_totals_and_groups_include_zero_values(statistics):
    assert (statistics.total, statistics.open) == (5, 3)
    assert statistics.by_category == {
        TicketCategory.HARDWARE: 2, TicketCategory.SOFTWARE: 1, TicketCategory.NETWORK: 1, TicketCategory.ACCOUNT: 1
    }
    assert statistics.by_status[TicketStatus.IN_PROGRESS] == 0  # hiç talebi olmayan durum da listede
    assert sum(statistics.by_status.values()) == 5


def test_resolution_time_and_sla(statistics):
    assert statistics.average_resolution_hours == 38.0  # (4 + 72) / 2
    sla = statistics.sla
    assert (sla.met, sla.breached, sla.open_overdue) == (1, 1, 1)
    assert sla.compliance_rate == 0.5


def test_ai_success_metrics(statistics):
    ai = statistics.ai
    assert ai.processed == 4  # OPEN dışındakiler
    assert (ai.answered, ai.low_confidence, ai.failed) == (2, 1, 1)
    assert (ai.helpful, ai.not_helpful) == (1, 1)
    assert ai.auto_resolution_rate == 0.25  # teknisyene gitmeden kapanan: 1 / 4
    assert ai.average_confidence == 0.67


def test_weekly_counts_cover_requested_weeks_including_empty_ones(statistics):
    assert statistics.weekly == [
        WeeklyCountView(week_start=date(2026, 9, 28), created=1, resolved=0),
        WeeklyCountView(week_start=date(2026, 10, 5), created=1, resolved=1),
        WeeklyCountView(week_start=date(2026, 10, 12), created=2, resolved=1),
    ]


def test_empty_read_model_gives_zeros_and_no_rates(session_factory):
    with session_factory() as session, session.begin():
        session.execute(delete(TicketSummaryModel))
    with session_factory() as session:
        empty = SqlStatisticsQueries(session).failure_statistics(ai_threshold=THRESHOLD, weeks=2, now=NOW)
    assert empty.total == 0
    assert empty.average_resolution_hours is None
    assert empty.sla.compliance_rate is None
    assert empty.ai.auto_resolution_rate is None
    assert [week.created for week in empty.weekly] == [0, 0]


# --- Handler: yetki ve parametre sınırları ---


class RecordingStatisticsQueries(StatisticsQueries):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def failure_statistics(self, *, ai_threshold, weeks, now):
        self.calls.append({"ai_threshold": ai_threshold, "weeks": weeks})
        return None


class FakeUsers(UserQueries):
    USERS = {
        1: UserView(1, "Yönetici", "y@x", UserRole.ADMIN, None, False, None),
        2: UserView(2, "Teknisyen", "t@x", UserRole.TECHNICIAN, None, False, SupportLevel.TIER_1),
    }

    def get(self, user_id):
        return self.USERS.get(user_id)

    def list_all(self):
        return list(self.USERS.values())


def test_only_admin_can_see_statistics():
    queries = RecordingStatisticsQueries()
    handler = GetFailureStatisticsHandler(queries, FakeUsers(), THRESHOLD)
    with pytest.raises(PermissionDeniedError):
        handler.handle(GetFailureStatisticsQuery(actor_id=2))
    assert queries.calls == []


@pytest.mark.parametrize(("requested", "used"), [(8, 8), (0, 1), (500, 52)])
def test_weeks_are_clamped_and_threshold_comes_from_settings(requested, used):
    queries = RecordingStatisticsQueries()
    GetFailureStatisticsHandler(queries, FakeUsers(), THRESHOLD).handle(
        GetFailureStatisticsQuery(actor_id=1, weeks=requested)
    )
    assert queries.calls == [{"ai_threshold": THRESHOLD, "weeks": used}]


# --- Endpoint ---


def test_statistics_endpoint(session_factory):
    uow = SqlAlchemyUnitOfWork(FakeEventBus(), session_factory)
    with uow:
        from app.domain.user import User

        admin = uow.users.add(User(full_name="İst Yön", email="stats.admin@test.edu", role=UserRole.ADMIN))
        user = uow.users.add(User(full_name="İst Kul", email="stats.user@test.edu"))
        uow.commit()

    app = create_app()

    def test_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = test_session
    client = TestClient(app)

    response = client.get("/statistics/failures?weeks=4", headers={"X-User-Id": str(admin.id)})
    assert response.status_code == 200
    body = response.json()
    assert len(body["weekly"]) == 4
    assert set(body["by_category"]) == {category.value for category in TicketCategory}
    assert {"answered", "low_confidence", "auto_resolution_rate"} <= set(body["ai"])

    assert client.get("/statistics/failures", headers={"X-User-Id": str(user.id)}).status_code == 403
    assert client.get("/statistics/failures?weeks=0", headers={"X-User-Id": str(admin.id)}).status_code == 422
