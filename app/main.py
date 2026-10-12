"""Uygulamanın giriş noktası: FastAPI nesnesini oluşturur ve router'ları bağlar."""

import logging

from fastapi import FastAPI

from app.api import devices, health, maintenance, tickets
from app.api.errors import register_exception_handlers
from app.core.config import get_settings
from app.core.dependencies import create_event_bus


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO if settings.debug else logging.WARNING,
        format="%(levelname)s:     %(name)s - %(message)s",
    )

    app = FastAPI(title=settings.app_name, debug=settings.debug)
    # Uygulama başına tek event bus; dinleyiciler oluşturulurken kaydedilir
    app.state.event_bus = create_event_bus()
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(devices.router)
    app.include_router(maintenance.router)
    app.include_router(tickets.router)
    return app


app = create_app()
