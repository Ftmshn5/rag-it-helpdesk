"""İş kuralı 5 ve ek yükleme yetkisinin domain testleri."""

import pytest

from app.domain.attachments import JPEG, PNG, validate_screenshot
from app.domain.enums import TicketCategory, TicketStatus, UserRole
from app.domain.errors import DomainError, InvalidFileError
from app.domain.ticket import Ticket
from app.domain.user import User

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 100
LIMIT = 1024


def test_png_and_jpeg_are_detected_by_content():
    assert validate_screenshot(PNG_BYTES, LIMIT) == PNG
    assert validate_screenshot(JPEG_BYTES, LIMIT) == JPEG


@pytest.mark.parametrize(
    "content",
    [
        b"GIF89a" + b"\x00" * 10,  # GIF
        b"%PDF-1.7 ...",  # PDF
        b"MZ\x90\x00 this is an exe renamed to .png",  # Windows çalıştırılabilir dosyası
        b"<svg xmlns='http://www.w3.org/2000/svg'/>",  # SVG (betik içerebilir)
    ],
)
def test_other_types_are_rejected_regardless_of_file_name(content):
    with pytest.raises(InvalidFileError, match="Yalnızca PNG veya JPG"):
        validate_screenshot(content, LIMIT)


def test_empty_file_is_rejected():
    with pytest.raises(InvalidFileError, match="boş"):
        validate_screenshot(b"", LIMIT)


def test_file_over_limit_is_rejected_and_limit_itself_is_allowed():
    exactly_limit = PNG_BYTES + b"\x00" * (LIMIT - len(PNG_BYTES))
    assert validate_screenshot(exactly_limit, LIMIT) == PNG

    with pytest.raises(InvalidFileError, match="en fazla"):
        validate_screenshot(exactly_limit + b"\x00", LIMIT)


def test_size_message_shows_megabytes():
    with pytest.raises(InvalidFileError, match="en fazla 5 MB"):
        validate_screenshot(PNG_BYTES + b"\x00" * (5 * 1024 * 1024), 5 * 1024 * 1024)


# --- Kim ek yükleyebilir? ---

REQUESTER = User(id=1, full_name="Ayşe", email="a@x.edu")
TECHNICIAN = User(id=2, full_name="Ali", email="t@x.edu", role=UserRole.TECHNICIAN)
OTHER_TECHNICIAN = User(id=3, full_name="Elif", email="e@x.edu", role=UserRole.TECHNICIAN)
ADMIN = User(id=4, full_name="Can", email="c@x.edu", role=UserRole.ADMIN)
STRANGER = User(id=5, full_name="Mehmet", email="m@x.edu")


def make_ticket(status: TicketStatus = TicketStatus.OPEN) -> Ticket:
    return Ticket(
        title="t", description="d", category=TicketCategory.SOFTWARE, requester_id=1, assignee_id=2, status=status
    )


@pytest.mark.parametrize(
    "user, allowed",
    [
        (REQUESTER, True),
        (TECHNICIAN, True),
        (ADMIN, True),
        (OTHER_TECHNICIAN, False),
        (STRANGER, False),
    ],
)
def test_who_can_attach(user, allowed):
    assert make_ticket().is_participant(user) is allowed


def test_closed_ticket_does_not_accept_contributions():
    ticket = make_ticket(TicketStatus.CLOSED)
    with pytest.raises(DomainError, match="Kapanmış talebe"):
        ticket.ensure_open_for_contributions()
