"""ticket_summary sla_layers

Talep detayında "SLA nasıl oluştu" açıklaması (Decorator zincirinin katmanları):
projektör her talep için [{"name", "sla_hours", "priority_score"}, …] yazar.
Mevcut satırlar boş liste ile başlar; doldurmak için read model'ler yeniden kurulur:
python -m app.infrastructure.db.projections

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-10-14 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'ticket_summary',
        sa.Column('sla_layers', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        schema='read',
    )
    # Varsayılan yalnızca mevcut satırlar içindi; yeni satırları projektör yazar (ORM modeliyle aynı)
    op.alter_column('ticket_summary', 'sla_layers', server_default=None, schema='read')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ticket_summary', 'sla_layers', schema='read')
