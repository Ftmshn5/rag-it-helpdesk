"""Kod stili kuralı: bir tasarım desenini uygulayan her sınıfın docstring'i desenin adını ve rolünü yazar.

CLAUDE.md: "Her tasarım deseninin uygulandığı sınıfın docstring'inde desenin adı
ve rolü yazılır." Bu tablo aynı zamanda sunum/rapor için "hangi desen hangi
sınıfta" listesidir; yeni bir desen sınıfı eklenince buraya da eklenir.
"""

import pytest

from app.application.commands.ticket_workflow import TicketTransitionHandler
from app.application.event_handlers import AutoAnswerScheduler
from app.application.interfaces.ai_support import AiSupportFacade
from app.application.interfaces.event_bus import EventBus, EventHandler
from app.application.interfaces.repositories import Repository
from app.application.interfaces.unit_of_work import UnitOfWork
from app.domain.inventory import MaintenanceRecord
from app.domain.ticket import Ticket
from app.domain.ticket_behavior import (
    BasicTicket,
    TicketComponent,
    TicketComponentFactory,
    TicketDecorator,
    UrgentTicket,
    VipTicket,
)
from app.domain.ticket_state import (
    AiAnsweredState,
    AssignedState,
    ClosedState,
    EscalatedState,
    InProgressState,
    OpenState,
    ResolvedState,
    TicketState,
)
from app.infrastructure.ai.fake_ai_support import FakeAiSupport
from app.infrastructure.ai.ollama import OllamaEmbeddingProvider, OllamaLlmProvider
from app.infrastructure.ai.providers import EmbeddingProvider, LlmProvider
from app.infrastructure.ai.rag_ai_support import RagAiSupport
from app.infrastructure.db.mappers import Mapper
from app.infrastructure.db.projections import DeviceInventoryProjector, Projector, TicketSummaryProjector
from app.infrastructure.db.repositories import SqlAlchemyRepository
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.events.event_logger import EventLogger
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus

PATTERN_CLASSES: dict[str, list[type]] = {
    "Facade": [AiSupportFacade, RagAiSupport, FakeAiSupport],
    "Strategy": [EmbeddingProvider, LlmProvider, OllamaEmbeddingProvider, OllamaLlmProvider],
    "Decorator": [TicketComponent, BasicTicket, TicketDecorator, VipTicket, UrgentTicket],
    "Factory": [TicketComponentFactory],
    "State": [
        Ticket,
        TicketState,
        OpenState,
        AiAnsweredState,
        EscalatedState,
        AssignedState,
        InProgressState,
        ResolvedState,
        ClosedState,
    ],
    "Observer": [EventBus, EventHandler, InMemoryEventBus, EventLogger, AutoAnswerScheduler, Projector],
    "Template Method": [TicketTransitionHandler, Projector, TicketSummaryProjector, DeviceInventoryProjector, UnitOfWork],
    "Repository": [Repository, SqlAlchemyRepository],
    "Unit of Work": [UnitOfWork, SqlAlchemyUnitOfWork],
    "Data Mapper": [Mapper],
}

CASES = [(pattern, cls) for pattern, classes in PATTERN_CLASSES.items() for cls in classes]


@pytest.mark.parametrize(("pattern", "cls"), CASES, ids=[f"{p}-{c.__name__}" for p, c in CASES])
def test_pattern_class_docstring_names_the_pattern(pattern, cls):
    docstring = cls.__doc__ or ""
    assert f"{pattern} deseni" in docstring, f"{cls.__name__} docstring'inde '{pattern} deseni' geçmiyor"


def test_factory_methods_name_their_pattern():
    for method in (Ticket.open, MaintenanceRecord.open):
        assert "Factory Method" in (method.__doc__ or "")
