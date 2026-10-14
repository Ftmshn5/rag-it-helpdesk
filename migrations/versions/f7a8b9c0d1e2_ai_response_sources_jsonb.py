"""ai_responses.sources: metin dizisi → JSONB (kaynak + kullanılan parçalar)

E4: AI yanıtının kaynakları artık doküman başlığı, dosya yolu ve AI'ın kullandığı
parçaların anlık kopyasını taşır. Eski kayıtların dosya yolları korunur (başlık olarak
dosya yolu, parça yok).

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-10-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ALTER ... USING alt sorgu kabul etmediği için yeni sütun → doldur → eskisini kaldır
    op.add_column(
        'ai_responses',
        sa.Column('sources_json', postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        schema='write',
    )
    op.execute(
        """
        UPDATE write.ai_responses SET sources_json = COALESCE(
            (SELECT jsonb_agg(jsonb_build_object('title', s, 'file_path', s, 'excerpts', '[]'::jsonb))
             FROM unnest(sources) AS s),
            '[]'::jsonb)
        """
    )
    op.drop_column('ai_responses', 'sources', schema='write')
    op.alter_column('ai_responses', 'sources_json', new_column_name='sources', schema='write')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'ai_responses',
        sa.Column('sources_text', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        schema='write',
    )
    op.execute(
        """
        UPDATE write.ai_responses SET sources_text = ARRAY(
            SELECT item->>'file_path' FROM jsonb_array_elements(sources) AS item)
        """
    )
    op.drop_column('ai_responses', 'sources', schema='write')
    op.alter_column('ai_responses', 'sources_text', new_column_name='sources', schema='write')
