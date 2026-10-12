"""knowledge_chunks embedding 1024 and hnsw index

Embedding modeli bge-m3 seçildi (çok dilli, Türkçe benzerlikte daha iyi);
vektör boyutu 768'den 1024'e çıkar. Boyut değişince eski vektörler anlamsız
olduğu için parçalar silinir; bilgi bankası yeniden indekslenir.

HNSW indeksi kosinüs uzaklığı (<=>) için kurulur: retriever "en yakın k parça"
sorgusunu bu operatörle yapar.

Revision ID: 8f20472d51d9
Revises: 7ac24ada8f52
Create Date: 2026-10-12 21:02:09.864870

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy  # noqa: F401  (Vector tipi için)


# revision identifiers, used by Alembic.
revision: str = '8f20472d51d9'
down_revision: Union[str, Sequence[str], None] = '7ac24ada8f52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _change_dimension(dimension: int) -> None:
    op.execute("DELETE FROM write.knowledge_chunks")
    op.execute("UPDATE write.knowledge_documents SET indexed_at = NULL")
    op.alter_column(
        'knowledge_chunks',
        'embedding',
        type_=pgvector.sqlalchemy.Vector(dimension),
        postgresql_using=f'embedding::vector({dimension})',
        schema='write',
    )


def upgrade() -> None:
    """Upgrade schema."""
    _change_dimension(1024)
    op.create_index(
        'ix_knowledge_chunks_embedding_hnsw',
        'knowledge_chunks',
        ['embedding'],
        schema='write',
        postgresql_using='hnsw',
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_knowledge_chunks_embedding_hnsw', table_name='knowledge_chunks', schema='write')
    _change_dimension(768)
