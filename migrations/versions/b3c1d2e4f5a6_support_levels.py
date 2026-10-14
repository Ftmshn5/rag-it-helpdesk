"""support levels (Chain of Responsibility)

Teknisyenlere destek seviyesi (TIER_1 / TIER_2), taleplere bulundukları seviye
(AI / TIER_1 / TIER_2) eklenir.

Mevcut veri: tüm teknisyenler L1 olur (kıdemli teknisyen yönetici tarafından
elle belirlenir; yeni kurulan veritabanında seed Elif Şahin'i L2 yapar).
AI'dan teknisyene geçmiş talepler L1 olur; geri kalanı (AI'ın yanıtladığı veya
AI ile kapanan) AI seviyesinde kalır.

Revision ID: b3c1d2e4f5a6
Revises: 8f20472d51d9
Create Date: 2026-10-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c1d2e4f5a6'
down_revision: Union[str, Sequence[str], None] = '8f20472d51d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('support_level', sa.String(length=32), nullable=True), schema='write')
    op.create_check_constraint(
        op.f('ck_users_support_level'), 'users', "support_level IN ('AI', 'TIER_1', 'TIER_2')", schema='write'
    )
    op.execute("UPDATE write.users SET support_level = 'TIER_1' WHERE role = 'TECHNICIAN'")

    op.add_column(
        'tickets',
        sa.Column('support_level', sa.String(length=32), server_default='AI', nullable=False),
        schema='write',
    )
    op.create_check_constraint(
        op.f('ck_tickets_support_level'), 'tickets', "support_level IN ('AI', 'TIER_1', 'TIER_2')", schema='write'
    )
    op.execute(
        """
        UPDATE write.tickets SET support_level = 'TIER_1'
        WHERE status IN ('ESCALATED', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED')
           OR (status = 'CLOSED' AND assignee_id IS NOT NULL)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('ck_tickets_support_level'), 'tickets', schema='write', type_='check')
    op.drop_column('tickets', 'support_level', schema='write')
    op.drop_constraint(op.f('ck_users_support_level'), 'users', schema='write', type_='check')
    op.drop_column('users', 'support_level', schema='write')
