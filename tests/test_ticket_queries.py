"""Talep sorguları: handler'lar (sahte), SQL implementasyonu ve API (gerçek PostgreSQL)."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.application.commands.ticket_workflow import AddCommentCommand, AddCommentHandler
from app.application.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from app.application.queries.tickets import (
    AiAnswerView,
    GetTicketDetailHandler,
    GetTicketDetailQuery,
    ListAllTicketsHandler,
    ListAllTicketsQuery,
    ListAssignedTicketsHandler,
    ListAssignedTicketsQuery,
    ListMyTicketsHandler,
    ListMyTicketsQuery,
    TicketDetailView,
    TicketQueries,
    TicketSummaryView,
)
from app.application.queries.users import UserQueries, UserView
from app.core.dependencies import get_db_session
from app.domain.enums import SupportLevel, TicketCategory, TicketModifier, TicketStatus, UserRole
from app.domain.ticket import AIResponse, Ticket
from app.domain.user import User
from app.infrastructure.db.projections import TicketSummaryProjector
from app.infrastructure.db.queries import SqlTicketQueries
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import create_app
from tests.fakes import FakeEventBus

S = TicketStatus
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)

# --- Handler testleri (sahte sorgularla, veritabanı yok) ---

USERS = {
    1: UserView(1, "Ayşe", "a@x.edu", UserRole.USER, None, False, None),
    2: UserView(2, "Ali", "t@x.edu", UserRole.TECHNICIAN, None, False, SupportLevel.TIER_1),
    3: UserView(3, "Can", "c@x.edu", UserRole.ADMIN, None, False, None),
    4: UserView(4, "Mehmet", "m@x.edu", UserRole.USER, None, False, None),
    5: UserView(5, "Elif", "e@x.edu", UserRole.TECHNICIAN, None, False, SupportLevel.TIER_1),
}
REQUESTER, TECH, ADMIN, STRANGER, OTHER_TECH = 1, 2, 3, 4, 5


class FakeUserQueries(UserQueries):
    def get(self, user_id):
        return USERS.get(user_id)

    def list_all(self):
        return list(USERS.values())


def summary(**overrides) -> TicketSummaryView:
    values = dict(
        ticket_id=10,
        title="t",
        category=TicketCategory.NETWORK,
        status=S.ASSIGNED,
        support_level=SupportLevel.TIER_1,
        requester_id=REQUESTER,
        requester_name="Ayşe",
        assignee_id=TECH,
        assignee_name="Ali",
        device_asset_tag=None,
        is_vip=False,
        is_urgent=False,
        sla_hours=72,
        priority_score=10,
        due_at=NOW,
        is_overdue=False,
        ai_confidence=None,
        ai_feedback=None,
        comment_count=0,
        attachment_count=0,
        created_at=NOW,
        resolved_at=None,
    )
    return TicketSummaryView(**(values | overrides))


class FakeTicketQueries(TicketQueries):
    def __init__(self, detail: TicketDetailView | None = None) -> None:
        self.detail = detail
        self.calls = []

    def list_by_requester(self, requester_id, status=None):
        self.calls.append(("requester", requester_id, status))
        return []

    def list_by_assignee(self, assignee_id, status=None):
        self.calls.append(("assignee", assignee_id, status))
        return []

    def list_all(self, status=None):
        self.calls.append(("all", status))
        return []

    def get_detail(self, ticket_id):
        return self.detail

    def get_attachment(self, ticket_id, attachment_id):
        return None


def test_my_tickets_are_filtered_by_actor_not_by_parameter():
    queries = FakeTicketQueries()
    ListMyTicketsHandler(queries, FakeUserQueries()).handle(ListMyTicketsQuery(actor_id=REQUESTER, status=S.OPEN))
    assert queries.calls == [("requester", REQUESTER, S.OPEN)]


def test_unknown_viewer_is_rejected():
    with pytest.raises(AuthenticationError):
        ListMyTicketsHandler(FakeTicketQueries(), FakeUserQueries()).handle(ListMyTicketsQuery(actor_id=99))


@pytest.mark.parametrize(
    "handler_class, query_class, allowed, denied",
    [
        (ListAssignedTicketsHandler, ListAssignedTicketsQuery, TECH, REQUESTER),
        (ListAllTicketsHandler, ListAllTicketsQuery, ADMIN, TECH),
    ],
)
def test_role_restricted_lists(handler_class, query_class, allowed, denied):
    handler = handler_class(FakeTicketQueries(), FakeUserQueries())
    handler.handle(query_class(actor_id=allowed))
    with pytest.raises(PermissionDeniedError):
        handler.handle(query_class(actor_id=denied))


def detail_query(actor_id: int) -> GetTicketDetailQuery:
    return GetTicketDetailQuery(actor_id=actor_id, ticket_id=10)


def detail_with_ai(confidence: float) -> TicketDetailView:
    return TicketDetailView(
        summary=summary(),
        description="d",
        ai_answer=AiAnswerView("Cevap", confidence, ["k.md"], None),
    )


@pytest.mark.parametrize("actor_id", [REQUESTER, TECH, ADMIN])
def test_participants_can_view_detail(actor_id):
    handler = GetTicketDetailHandler(FakeTicketQueries(detail_with_ai(0.9)), FakeUserQueries(), 0.6)
    assert handler.handle(detail_query(actor_id)).ai_answer.answer == "Cevap"


@pytest.mark.parametrize("actor_id", [STRANGER, OTHER_TECH])
def test_others_cannot_view_detail(actor_id):
    handler = GetTicketDetailHandler(FakeTicketQueries(detail_with_ai(0.9)), FakeUserQueries(), 0.6)
    with pytest.raises(PermissionDeniedError):
        handler.handle(detail_query(actor_id))


def test_missing_ticket_raises_not_found():
    handler = GetTicketDetailHandler(FakeTicketQueries(None), FakeUserQueries(), 0.6)
    with pytest.raises(NotFoundError):
        handler.handle(detail_query(REQUESTER))


def test_low_confidence_answer_is_hidden_from_requester_but_visible_to_staff():
    handler = GetTicketDetailHandler(FakeTicketQueries(detail_with_ai(0.3)), FakeUserQueries(), 0.6)

    assert handler.handle(detail_query(REQUESTER)).ai_answer is None
    assert handler.handle(detail_query(TECH)).ai_answer.confidence == 0.3
    assert handler.handle(detail_query(ADMIN)).ai_answer.confidence == 0.3


# --- SQL implementasyonu (gerçek PostgreSQL) ---


@pytest.fixture
def data(session_factory):
    """Üç talep: normal, VIP ve VIP+Acil; hepsi aynı teknisyene atanmış."""
    uow = SqlAlchemyUnitOfWork(FakeEventBus(), session_factory)
    with uow:
        user = uow.users.add(User(full_name="Q Kullanıcı", email="q.user@test.edu"))
        tech = uow.users.add(
            User(full_name="Q Teknisyen", email="q.tech@test.edu", role=UserRole.TECHNICIAN)
        )
        base = dict(
            description="Açıklama metni",
            category=TicketCategory.HARDWARE,
            requester_id=user.id,
            assignee_id=tech.id,
            status=S.ASSIGNED,
        )
        old = datetime.now(UTC) - timedelta(days=5)
        normal = uow.tickets.add(Ticket(title="Normal", created_at=old, **base))
        vip = uow.tickets.add(Ticket(title="VIP", modifiers=[TicketModifier.VIP], **base))
        urgent = uow.tickets.add(
            Ticket(
                title="Acil", modifiers=[TicketModifier.VIP, TicketModifier.URGENT], **base
            )
        )
        resolved = uow.tickets.add(
            Ticket(title="Çözüldü", created_at=old, **(base | {"status": S.RESOLVED}))
        )
        uow.ai_responses.add(
            AIResponse(ticket_id=vip.id, answer="Yeniden başlatın.", confidence=0.7, sources=["k.md"])
        )
        uow.commit()
    AddCommentHandler(uow).handle(AddCommentCommand(actor_id=tech.id, ticket_id=vip.id, content="Bakıyorum."))
    TicketSummaryProjector(session_factory).rebuild()
    return user, tech, normal, vip, urgent, resolved


def test_assigned_list_is_ordered_as_work_queue(session_factory, data):
    _, tech, normal, vip, urgent, resolved = data
    with session_factory() as session:
        rows = SqlTicketQueries(session).list_by_assignee(tech.id)

    # Öncelik puanı (Decorator): Acil+VIP 80 > VIP 30 > normal 10
    assert [r.title for r in rows if r.status == S.ASSIGNED] == ["Acil", "VIP", "Normal"]
    assert [r.priority_score for r in rows[:3]] == [80, 30, 10]


def test_status_filter(session_factory, data):
    _, tech, *_ = data
    with session_factory() as session:
        rows = SqlTicketQueries(session).list_by_assignee(tech.id, S.RESOLVED)
    assert [r.title for r in rows] == ["Çözüldü"]


def test_overdue_is_computed_at_read_time(session_factory, data):
    user, *_ = data
    with session_factory() as session:
        rows = {r.title: r for r in SqlTicketQueries(session).list_by_requester(user.id)}

    assert rows["Normal"].is_overdue  # 5 gün önce açıldı, SLA 72 saat
    assert not rows["Acil"].is_overdue  # yeni açıldı
    assert not rows["Çözüldü"].is_overdue  # çözülmüş talep gecikmiş sayılmaz


def test_detail_combines_read_model_and_write_tables(session_factory, data):
    _, _, _, vip, *_ = data
    with session_factory() as session:
        detail = SqlTicketQueries(session).get_detail(vip.id)

    assert detail.description == "Açıklama metni"
    assert detail.summary.sla_hours == 24
    assert detail.ai_answer == AiAnswerView("Yeniden başlatın.", 0.7, ["k.md"], None)
    assert [(c.author_name, c.content) for c in detail.comments] == [("Q Teknisyen", "Bakıyorum.")]
    assert detail.summary.comment_count == 1


# --- API (gerçek PostgreSQL) ---


def test_query_endpoints(session_factory, data):
    user, tech, normal, vip, *_ = data
    app = create_app()

    def test_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = test_session
    client = TestClient(app)

    mine = client.get("/tickets/mine", headers={"X-User-Id": str(user.id)})
    assert mine.status_code == 200
    assert {t["title"] for t in mine.json()} == {"Normal", "VIP", "Acil", "Çözüldü"}

    queue = client.get("/tickets/assigned?status=ASSIGNED", headers={"X-User-Id": str(tech.id)})
    assert [t["title"] for t in queue.json()] == ["Acil", "VIP", "Normal"]

    forbidden = client.get("/tickets/assigned", headers={"X-User-Id": str(user.id)})
    assert forbidden.status_code == 403

    detail = client.get(f"/tickets/{vip.id}", headers={"X-User-Id": str(user.id)})
    assert detail.status_code == 200
    body = detail.json()
    assert body["ai_answer"]["answer"] == "Yeniden başlatın."
    assert body["summary"]["sla_hours"] == 24
    assert body["comments"][0]["author_name"] == "Q Teknisyen"

    assert client.get("/users").status_code == 200
