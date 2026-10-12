import pytest

from app.application.interfaces.ai_support import AiSupportFacade
from app.domain.enums import TicketCategory
from app.domain.ticket import Ticket
from app.infrastructure.ai.fake_ai_support import FakeAiSupport


def make_ticket(title: str, description: str = "") -> Ticket:
    return Ticket(
        title=title, description=description, category=TicketCategory.SOFTWARE, requester_id=1
    )


def test_fake_implements_the_facade_interface():
    assert isinstance(FakeAiSupport(), AiSupportFacade)


@pytest.mark.parametrize(
    "title, description, confidence, source",
    [
        ("Şifremi unuttum", "", 0.85, "knowledge/hesap-sifre-sifirlama.md"),
        ("Bağlanamıyorum", "EDUROAM ağına bağlanmıyor", 0.75, "knowledge/kablosuz-ag-baglantisi.md"),
        ("YAZICI çalışmıyor", "", 0.70, "knowledge/yazici-sorunlari.md"),
    ],
)
def test_known_problems_get_confident_answer_with_source(title, description, confidence, source):
    result = FakeAiSupport().try_auto_resolve(make_ticket(title, description))

    assert result.confidence == confidence
    assert result.sources == [source]
    assert result.answer


def test_unknown_problem_gets_low_confidence_without_sources():
    result = FakeAiSupport().try_auto_resolve(make_ticket("Monitörden duman çıkıyor"))

    assert result.confidence < 0.6
    assert result.sources == []


def test_turkish_capital_i_is_matched():
    """'İNTERNET' küçük harfe çevrilirken bozulmamalı."""
    result = FakeAiSupport().try_auto_resolve(make_ticket("İNTERNET YOK"))
    assert result.confidence == 0.75


def test_same_ticket_always_gets_same_answer():
    ticket = make_ticket("Wi-Fi kopuyor")
    assert FakeAiSupport().try_auto_resolve(ticket) == FakeAiSupport().try_auto_resolve(ticket)
