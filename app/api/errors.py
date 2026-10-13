"""Domain/application hatalarını HTTP yanıtlarına çeviren tek yer.

Handler'lar HTTP'yi bilmez, yalnızca anlamlı hatalar fırlatır; durum koduna
karar vermek API katmanının işidir.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.application.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from app.domain.errors import DomainError, InvalidFileError


class HttpErrorMapper:
    """Hata türü → HTTP durum kodu eşlemesini uygulamaya kaydeder."""

    STATUS_CODES: dict[type[Exception], int] = {
        AuthenticationError: status.HTTP_401_UNAUTHORIZED,
        PermissionDeniedError: status.HTTP_403_FORBIDDEN,
        NotFoundError: status.HTTP_404_NOT_FOUND,
        # 409 Conflict: istek geçerli ama kaynağın mevcut durumuyla çelişiyor.
        # Tüm domain hataları tek taban sınıftan türediği için tek satır yeterli;
        # yeni bir kural hatası eklemek bu dosyayı değiştirmez (açık/kapalı ilkesi).
        DomainError: status.HTTP_409_CONFLICT,
        # Alt sınıf: geçersiz dosya bir durum çatışması değil, geçersiz veridir.
        # Starlette en özel (alt) sınıfın handler'ını seçer.
        InvalidFileError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    }

    def register(self, app: FastAPI) -> None:
        for error_class, status_code in self.STATUS_CODES.items():
            app.add_exception_handler(error_class, self._handler_for(status_code))
        app.add_exception_handler(RequestValidationError, self._validation_error)

    @staticmethod
    def _handler_for(status_code: int) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
        async def handler(request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})

        return handler

    @staticmethod
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
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
