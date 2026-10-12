"""Uygulamanın giriş noktası: FastAPI nesnesini oluşturur ve router'ları bağlar."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import devices, health, maintenance, queries, tickets
from app.api.errors import register_exception_handlers
from app.core.config import get_settings
from app.core.dependencies import create_event_bus, resume_pending_auto_answers
from app.infrastructure.events.task_runner import BackgroundTaskRunner, TaskRunner

logger = logging.getLogger(__name__)


def create_app(task_runner: TaskRunner | None = None) -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO if settings.debug else logging.WARNING,
        format="%(levelname)s:     %(name)s - %(message)s",
    )

    # Yavaş işler (AI yanıtı) için tek işçili arka plan kuyruğu
    runner = task_runner or BackgroundTaskRunner(thread_name_prefix="ai")
    # Uygulama başına tek event bus; dinleyiciler oluşturulurken kaydedilir
    event_bus = create_event_bus(runner)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            count = resume_pending_auto_answers(event_bus, runner)
            if count:
                logger.info("AI yanıtı bekleyen %s talep yeniden kuyruğa alındı", count)
        except Exception:
            # Veritabanı kapalıysa uygulama yine açılsın (/health durumu gösterir)
            logger.exception("Bekleyen AI işleri kuyruğa alınamadı")
        yield
        runner.shutdown()

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    # Frontend ayrı bir adreste çalışır; tarayıcının isteklere izin vermesi için CORS gerekir
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],  # X-User-Id dahil
    )
    app.state.event_bus = event_bus
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(devices.router)
    app.include_router(maintenance.router)
    app.include_router(tickets.router)
    app.include_router(queries.router)
    return app


app = create_app()
