"""Sağlık kontrolü endpoint'i: uygulama ayakta mı, veritabanına ulaşabiliyor mu?"""

from fastapi import APIRouter, Depends, Response, status

from app.core.dependencies import get_database_status

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response, database_ok: bool = Depends(get_database_status)) -> dict:
    if not database_ok:
        # 503: servis çalışıyor ama bağımlılığı (DB) hazır değil
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "error",
            "database": "unavailable",
            "detail": "Veritabanına bağlanılamadı.",
        }
    return {"status": "ok", "database": "ok"}
