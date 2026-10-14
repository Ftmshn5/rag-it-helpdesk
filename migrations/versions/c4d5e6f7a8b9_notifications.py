"""notifications

Kullanıcı bildirimleri (Observer + Strategy): her kanal (uygulama içi, e-posta,
SMS) kaydedilir; e-posta ve SMS teslimi benzetimdir.

Revision ID: c4d5e6f7a8b9
Revises: b3c1d2e4f5a6
Create Date: 2026-10-14 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c1d2e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=True),
        sa.Column(
            'channel',
            sa.Enum('IN_APP', 'EMAIL', 'SMS', name='channel', native_enum=False, create_constraint=True, length=32),
            nullable=False,
        ),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['recipient_id'], ['write.users.id'], name=op.f('fk_notifications_recipient_id_users')
        ),
        sa.ForeignKeyConstraint(
            ['ticket_id'], ['write.tickets.id'], name=op.f('fk_notifications_ticket_id_tickets'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications')),
        schema='write',
    )
    op.create_index(
        'ix_notifications_recipient_created', 'notifications', ['recipient_id', 'created_at'], schema='write'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_notifications_recipient_created', table_name='notifications', schema='write')
    op.drop_table('notifications', schema='write')
