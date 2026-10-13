"""Arıza istatistiklerinin SQL implementasyonu (read.ticket_summary üzerinde toplama sorguları)."""

from datetime import UTC, date, datetime, time, timedelta
from typing import TypeVar

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from app.application.queries.statistics import (
    AiStatisticsView,
    FailureStatisticsView,
    SlaStatisticsView,
    StatisticsQueries,
    WeeklyCountView,
)
from app.domain.enums import AiFeedback, TicketCategory, TicketStatus
from app.infrastructure.db.read_models import TicketSummaryModel

SECONDS_PER_HOUR = 3600
GroupEnum = TypeVar("GroupEnum", TicketCategory, TicketStatus)


class SqlStatisticsQueries(StatisticsQueries):
    """Göstergeler PostgreSQL'in FILTER ifadesiyle tek sorguda toplanır (gösterge başına ayrı sorgu yok)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def failure_statistics(self, *, ai_threshold: float, weeks: int, now: datetime) -> FailureStatisticsView:
        t = TicketSummaryModel
        finished = t.status.in_([TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value])
        processed = t.status != TicketStatus.OPEN.value
        resolution_seconds = func.extract("epoch", t.resolved_at - t.created_at)

        row = self._session.execute(
            select(
                func.count().label("total"),
                func.count().filter(~finished).label("open"),
                func.avg(resolution_seconds).filter(t.resolved_at.is_not(None)).label("avg_resolution_seconds"),
                func.count().filter(t.resolved_at <= t.due_at).label("sla_met"),
                func.count().filter(t.resolved_at > t.due_at).label("sla_breached"),
                func.count().filter(~finished, t.due_at < now).label("open_overdue"),
                func.count().filter(processed).label("ai_processed"),
                func.count().filter(t.ai_confidence >= ai_threshold).label("ai_answered"),
                func.count().filter(t.ai_confidence < ai_threshold).label("ai_low_confidence"),
                func.count().filter(t.ai_confidence.is_(None), processed).label("ai_failed"),
                func.count().filter(t.ai_feedback == AiFeedback.HELPFUL.value).label("ai_helpful"),
                func.count().filter(t.ai_feedback == AiFeedback.NOT_HELPFUL.value).label("ai_not_helpful"),
                func.avg(t.ai_confidence).label("ai_average_confidence"),
            )
        ).one()

        met, breached = row.sla_met, row.sla_breached
        return FailureStatisticsView(
            generated_at=now,
            total=row.total,
            open=row.open,
            by_category=self._counts_by(t.category, TicketCategory),
            by_status=self._counts_by(t.status, TicketStatus),
            weekly=self._weekly(weeks, now),
            average_resolution_hours=self._hours(row.avg_resolution_seconds),
            sla=SlaStatisticsView(
                met=met,
                breached=breached,
                open_overdue=row.open_overdue,
                compliance_rate=self._ratio(met, met + breached),
            ),
            ai=AiStatisticsView(
                processed=row.ai_processed,
                answered=row.ai_answered,
                low_confidence=row.ai_low_confidence,
                failed=row.ai_failed,
                helpful=row.ai_helpful,
                not_helpful=row.ai_not_helpful,
                auto_resolution_rate=self._ratio(row.ai_helpful, row.ai_processed),
                average_confidence=round(float(row.ai_average_confidence), 2)
                if row.ai_average_confidence is not None
                else None,
            ),
        )

    def _counts_by(self, column: ColumnElement[str], enum: type[GroupEnum]) -> dict[GroupEnum, int]:
        """Grup sayıları; hiç talebi olmayan değerler de 0 ile listelenir (grafikte boşluk kalmasın)."""
        counts = dict(self._session.execute(select(column, func.count()).group_by(column)).all())
        return {member: counts.get(member.value, 0) for member in enum}

    def _weekly(self, weeks: int, now: datetime) -> list[WeeklyCountView]:
        """Son `weeks` haftanın (bu hafta dahil, pazartesi başlangıçlı, UTC) açılan ve çözülen talep sayıları."""
        this_monday = now.astimezone(UTC).date() - timedelta(days=now.astimezone(UTC).weekday())
        week_starts = [this_monday - timedelta(weeks=offset) for offset in reversed(range(weeks))]
        since = datetime.combine(week_starts[0], time.min, tzinfo=UTC)

        created = self._count_per_week(TicketSummaryModel.created_at, since)
        resolved = self._count_per_week(TicketSummaryModel.resolved_at, since)
        return [
            WeeklyCountView(week_start=week, created=created.get(week, 0), resolved=resolved.get(week, 0))
            for week in week_starts
        ]

    def _count_per_week(self, column: ColumnElement[datetime], since: datetime) -> dict[date, int]:
        # Saat dilimi kaymasın diye hafta UTC'ye göre kesilir
        week = func.date_trunc("week", func.timezone("UTC", column)).label("week")
        statement: Select[tuple[datetime, int]] = (
            select(week, func.count()).where(column >= since).group_by(week)
        )
        return {week_start.date(): count for week_start, count in self._session.execute(statement)}

    @staticmethod
    def _ratio(part: int, whole: int) -> float | None:
        return round(part / whole, 3) if whole else None

    @staticmethod
    def _hours(seconds: float | None) -> float | None:
        return round(float(seconds) / SECONDS_PER_HOUR, 1) if seconds is not None else None
