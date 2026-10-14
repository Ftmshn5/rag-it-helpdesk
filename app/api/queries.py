"""Okuma endpoint'leri (CQRS okuma tarafı).

Yazma endpoint'lerinden ayrı bir router'dadır: tümü GET, hiçbiri veri değiştirmez.
Router fonksiyonları incedir: HTTP parametrelerinden bir Query nesnesi kurar,
handler'a verir ve sonucu döner; iş mantığı veya yetki kontrolü içermez.

Sabit yollar (/tickets/mine) değişkenli yoldan (/tickets/{ticket_id}) önce
tanımlanır; aksi halde "mine" bir talep numarası sanılırdı.
"""

from fastapi import APIRouter, Depends, Query, Response

from app.application.queries.inventory import (
    DeviceInventoryView,
    GetDeviceHandler,
    GetDeviceQuery,
    GetInventoryReportHandler,
    GetInventoryReportQuery,
    GetMaintenanceHistoryHandler,
    GetMaintenanceHistoryQuery,
    InventoryReportView,
    ListDevicesHandler,
    ListDevicesQuery,
    ListMyDevicesHandler,
    ListMyDevicesQuery,
    MaintenanceRecordView,
)
from app.application.queries.statistics import (
    FailureStatisticsView,
    GetFailureStatisticsHandler,
    GetFailureStatisticsQuery,
)
from app.application.queries.tickets import (
    GetAttachmentFileHandler,
    GetAttachmentFileQuery,
    GetTicketDetailHandler,
    GetTicketDetailQuery,
    ListAllTicketsHandler,
    ListAllTicketsQuery,
    ListAssignedTicketsHandler,
    ListAssignedTicketsQuery,
    ListMyTicketsHandler,
    ListMyTicketsQuery,
    TicketDetailView,
    TicketSummaryView,
)
from app.application.queries.users import ListUsersHandler, ListUsersQuery, UserView
from app.core.dependencies import (
    get_attachment_file_handler,
    get_current_user_id,
    get_device_handler,
    get_failure_statistics_handler,
    get_inventory_report_handler,
    get_list_all_tickets_handler,
    get_list_assigned_tickets_handler,
    get_list_devices_handler,
    get_list_my_devices_handler,
    get_list_my_tickets_handler,
    get_list_users_handler,
    get_maintenance_history_handler,
    get_ticket_detail_handler,
)
from app.domain.enums import DeviceStatus, TicketStatus

router = APIRouter(tags=["queries"])


@router.get("/users", response_model=list[UserView])
def list_users(handler: ListUsersHandler = Depends(get_list_users_handler)) -> list[UserView]:
    """Kimlik doğrulama kapsam dışı: arayüzdeki kullanıcı seçme kutusu bu listeyi kullanır."""
    return handler.handle(ListUsersQuery())


@router.get("/tickets/mine", response_model=list[TicketSummaryView])
def list_my_tickets(
    status: TicketStatus | None = None,
    actor_id: int = Depends(get_current_user_id),
    handler: ListMyTicketsHandler = Depends(get_list_my_tickets_handler),
) -> list[TicketSummaryView]:
    return handler.handle(ListMyTicketsQuery(actor_id=actor_id, status=status))


@router.get("/tickets/assigned", response_model=list[TicketSummaryView])
def list_assigned_tickets(
    status: TicketStatus | None = None,
    actor_id: int = Depends(get_current_user_id),
    handler: ListAssignedTicketsHandler = Depends(get_list_assigned_tickets_handler),
) -> list[TicketSummaryView]:
    return handler.handle(ListAssignedTicketsQuery(actor_id=actor_id, status=status))


@router.get("/tickets", response_model=list[TicketSummaryView])
def list_all_tickets(
    status: TicketStatus | None = None,
    actor_id: int = Depends(get_current_user_id),
    handler: ListAllTicketsHandler = Depends(get_list_all_tickets_handler),
) -> list[TicketSummaryView]:
    return handler.handle(ListAllTicketsQuery(actor_id=actor_id, status=status))


@router.get("/tickets/{ticket_id}/attachments/{attachment_id}")
def get_attachment_file(
    ticket_id: int,
    attachment_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: GetAttachmentFileHandler = Depends(get_attachment_file_handler),
) -> Response:
    attachment = handler.handle(
        GetAttachmentFileQuery(actor_id=actor_id, ticket_id=ticket_id, attachment_id=attachment_id)
    )
    return Response(
        content=attachment.content,
        media_type=attachment.mime_type,
        headers={
            # Tarayıcı türü tahmin etmeye çalışmasın: yalnızca bildirilen png/jpg
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/tickets/{ticket_id}", response_model=TicketDetailView)
def get_ticket_detail(
    ticket_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: GetTicketDetailHandler = Depends(get_ticket_detail_handler),
) -> TicketDetailView:
    return handler.handle(GetTicketDetailQuery(actor_id=actor_id, ticket_id=ticket_id))


# --- Envanter ---


@router.get("/inventory/report", response_model=InventoryReportView)
def get_inventory_report(
    status: DeviceStatus | None = None,
    type: str | None = None,
    actor_id: int = Depends(get_current_user_id),
    handler: GetInventoryReportHandler = Depends(get_inventory_report_handler),
) -> InventoryReportView:
    return handler.handle(GetInventoryReportQuery(actor_id=actor_id, status=status, device_type=type))


@router.get("/devices", response_model=list[DeviceInventoryView])
def list_devices(
    status: DeviceStatus | None = None,
    type: str | None = None,
    actor_id: int = Depends(get_current_user_id),
    handler: ListDevicesHandler = Depends(get_list_devices_handler),
) -> list[DeviceInventoryView]:
    return handler.handle(ListDevicesQuery(actor_id=actor_id, status=status, device_type=type))


@router.get("/devices/mine", response_model=list[DeviceInventoryView])
def list_my_devices(
    actor_id: int = Depends(get_current_user_id),
    handler: ListMyDevicesHandler = Depends(get_list_my_devices_handler),
) -> list[DeviceInventoryView]:
    return handler.handle(ListMyDevicesQuery(actor_id=actor_id))


# /devices/mine'dan SONRA tanımlanır: aksi halde "mine" bir cihaz numarası sanılıp 422 dönerdi
@router.get("/devices/{device_id}", response_model=DeviceInventoryView)
def get_device(
    device_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: GetDeviceHandler = Depends(get_device_handler),
) -> DeviceInventoryView:
    """E5: cihaz detayı (QR etiketi). Zimmet sahibi yalnızca personel ve sahibine görünür."""
    return handler.handle(GetDeviceQuery(actor_id=actor_id, device_id=device_id))


@router.get("/devices/{device_id}/maintenance-records", response_model=list[MaintenanceRecordView])
def get_maintenance_history(
    device_id: int,
    actor_id: int = Depends(get_current_user_id),
    handler: GetMaintenanceHistoryHandler = Depends(get_maintenance_history_handler),
) -> list[MaintenanceRecordView]:
    return handler.handle(GetMaintenanceHistoryQuery(actor_id=actor_id, device_id=device_id))


# --- İstatistik ---


@router.get("/statistics/failures", response_model=FailureStatisticsView)
def get_failure_statistics(
    weeks: int = Query(default=8, ge=1, le=52),
    actor_id: int = Depends(get_current_user_id),
    handler: GetFailureStatisticsHandler = Depends(get_failure_statistics_handler),
) -> FailureStatisticsView:
    """UC-12: yönetici arıza istatistikleri (kategori, zaman, SLA, AI başarısı)."""
    return handler.handle(GetFailureStatisticsQuery(actor_id=actor_id, weeks=weeks))
