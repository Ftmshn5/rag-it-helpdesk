"""Domain/application hatalarını HTTP yanıtlarına çeviren tek yer.

Handler'lar HTTP'yi bilmez, yalnızca anlamlı hatalar fırlatır; durum koduna
karar vermek API katmanının işidir.
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.application.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from app.domain.errors import BusinessRuleViolation

ERROR_STATUS_CODES: dict[type[Exception], int] = {
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    # 409 Conflict: istek geçerli ama kaynağın mevcut durumuyla çelişiyor
    BusinessRuleViolation: status.HTTP_409_CONFLICT,
}


def register_exception_handlers(app: FastAPI) -> None:
    for error_class, status_code in ERROR_STATUS_CODES.items():
        app.add_exception_handler(error_class, _make_handler(status_code))

    app.add_exception_handler(RequestValidationError, _validation_error_handler)


def _make_handler(status_code: int):
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic'in ayrıntılı (İngilizce) hata listesi "errors" altında korunur;
    # kullanıcıya gösterilecek özet mesaj Türkçedir.
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": "Gönderilen veriler geçersiz. Lütfen alanları kontrol edin.",
            "errors": [
                {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
                for error in exc.errors()
            ],
        },
    )
