"""Okuma endpoint'leri (CQRS okuma tarafı).

Yazma endpoint'lerinden ayrı bir router'dadır: tümü GET, hiçbiri veri değiştirmez.
Sabit yollar (/tickets/mine) değişkenli yoldan (/tickets/{ticket_id}) önce
tanımlanır; aksi halde "mine" bir talep numarası sanılırdı.
"""

from fastapi import APIRouter, Depends

from app.application.queries.tickets import (
    GetTicketDetailHandler,
    ListAllTicketsHandler,
    ListAssignedTicketsHandler,
    ListMyTicketsHandler,
    TicketDetailView,
    TicketSummaryView,
)
from app.application.queries.users import ListUsersHandler, UserView
from app.core.dependencies import (
    get_current_user_id,
    get_list_all_tickets_handler,
    get_list_assigned_tickets_handler,
    get_list_my_tickets_handler,
    get_list_users_handler,
    get_ticket_detail_handler,
)
from app.domain.enums import TicketStatus

router = APIRouter(tags=["queries"])


@router.get("/users", response_model=list[UserView])
def list_users(handler: ListUsersHandler = Depends(get_list_users_handler)):
    """Kimlik doğrulama kapsam dışı: arayüzdeki kullanıcı seçme kutusu bu listeyi kullanır."""
    return handler.handle()


@router.get("/tickets/mine", response_model=list[TicketSummaryView])
def list_my_tickets(
    status: TicketStatus | None = None,
    actor_id: int = Depends(get_current_user_id),
    handler: ListMyTicketsHandler = Depends(get_list_my_tickets_handler),
):
    return handler.handle(actor_id, status)


@router.get("/tickets/assigned", response_model=list[TicketSummaryView])
def list_assigned_tickets(
    status: TicketStatus | None = None,
    actor_id: int = Depends(get_current_user_id),
    handler: ListAssignedTicketsHandler = Depends(get_list_assigned_tickets_handler),
):
    return handler.handle(actor_id, status)


@router.get("/tickets", response_model=list[TicketSummaryView])
def list_all_tickets(
    status: TicketStatus | None = None,
    actor_id: int = Depends(get_current_user_id),
    handler: ListAllTicketsHandler = Depends(get_list_all_tickets_handler),
):
    return handler.handle(actor_id, status)


@router.get("/tickets/{ticket_id}", response_model=TicketDetailView)
def get_ticket_detail(
    ticket_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: GetTicketDetailHandler = Depends(get_ticket_detail_handler),
):
    return handler.handle(actor_id, ticket_id)
