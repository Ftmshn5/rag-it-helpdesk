"""Uygulamanın giriş noktası: FastAPI nesnesini oluşturur ve router'ları bağlar."""

import logging

from fastapi import FastAPI

from app.api import health
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
    app.include_router(health.router)
    return app


app = create_app()
