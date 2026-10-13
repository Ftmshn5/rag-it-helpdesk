"""Arıza istatistikleri (UC-12, CQRS okuma tarafı).

Kaynak: denormalize read model (read.ticket_summary). Ayrı bir istatistik
tablosu tutulmaz; toplama sorguları aynı read model üzerinde çalışır. Ayrı bir
tablo, tutarlı tutulması gereken ikinci bir kopya olurdu; bu ölçekte gereksiz.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from app.application.queries.base import ActorQuery, QueryHandler
from app.application.queries.users import UserQueries
from app.domain.clock import Clock
from app.domain.enums import TicketCategory, TicketStatus, UserRole


@dataclass(frozen=True)
class WeeklyCountView:
    week_start: date  # haftanın pazartesi günü
    created: int
    resolved: int


@dataclass(frozen=True)
class SlaStatisticsView:
    met: int  # son tarihten önce çözülen
    breached: int  # son tarihten sonra çözülen
    open_overdue: int  # çözülmemiş ve süresi geçmiş
    compliance_rate: float | None  # met / (met + breached); çözülmüş talep yoksa None


@dataclass(frozen=True)
class AiStatisticsView:
    """İş kuralı 4'e göre AI'ın talepler üzerindeki etkisi."""

    processed: int  # AI'ın ele aldığı (OPEN olmayan) talepler
    answered: int  # güven eşiğin üstünde: yanıt kullanıcıya gösterildi
    low_confidence: int  # güven eşiğin altında: yanıt gizlendi, talep eskale edildi
    failed: int  # AI yanıt üretemedi (hata) → eskale
    helpful: int  # kullanıcı "çözüldü" dedi
    not_helpful: int  # kullanıcı "çözülmedi" dedi
    auto_resolution_rate: float | None  # helpful / processed: teknisyene hiç gitmeden kapanan oran
    average_confidence: float | None


@dataclass(frozen=True)
class FailureStatisticsView:
    generated_at: datetime
    total: int
    open: int  # çözülmemiş (RESOLVED/CLOSED dışı)
    by_category: dict[TicketCategory, int]
    by_status: dict[TicketStatus, int]
    weekly: list[WeeklyCountView]
    average_resolution_hours: float | None
    sla: SlaStatisticsView
    ai: AiStatisticsView


class StatisticsQueries(ABC):
    """İstatistik okuma arayüzü; SQL implementasyonu infrastructure/db/statistics.py'de."""

    @abstractmethod
    def failure_statistics(self, *, ai_threshold: float, weeks: int, now: datetime) -> FailureStatisticsView: ...


@dataclass(frozen=True, kw_only=True)
class GetFailureStatisticsQuery(ActorQuery):
    weeks: int = 8  # haftalık grafikte kaç hafta geriye gidilsin (bu hafta dahil)


class GetFailureStatisticsHandler(QueryHandler[GetFailureStatisticsQuery, FailureStatisticsView]):
    """UC-12: yönetici arıza istatistiklerini görür."""

    MAX_WEEKS = 52

    def __init__(self, statistics: StatisticsQueries, users: UserQueries, ai_threshold: float) -> None:
        super().__init__(users)
        self._statistics = statistics
        self._ai_threshold = ai_threshold

    def handle(self, query: GetFailureStatisticsQuery) -> FailureStatisticsView:
        self._require_viewer(query.actor_id, UserRole.ADMIN)
        weeks = min(max(query.weeks, 1), self.MAX_WEEKS)
        return self._statistics.failure_statistics(ai_threshold=self._ai_threshold, weeks=weeks, now=Clock.now())
