"""ticket_timeline

Talep zaman çizelgesi read model'i (E3): event bus'a yayınlanan talep olayları satır
olarak eklenir (yalnızca eklenir). Mevcut talepler için bilinenler (oluşturulma, notlar,
ekler) şu komutla doldurulur; durum geçmişi olaylarda olduğundan geriye dönük kurulamaz:
python -m app.infrastructure.db.projections

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-10-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ticket_timeline',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('actor_name', sa.String(length=120), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ticket_timeline')),
        schema='read',
    )
    op.create_index(
        'ix_ticket_timeline_ticket_occurred', 'ticket_timeline', ['ticket_id', 'occurred_at'], schema='read'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_ticket_timeline_ticket_occurred', table_name='ticket_timeline', schema='read')
    op.drop_table('ticket_timeline', schema='read')
