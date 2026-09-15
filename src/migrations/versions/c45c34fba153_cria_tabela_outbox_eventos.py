"""cria tabela outbox eventos

Revision ID: c45c34fba153
Revises: 202609140002
Create Date: 2026-09-15 09:18:28.535745

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c45c34fba153"
down_revision: Union[str, Sequence[str], None] = "202609140002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "outbox_eventos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tipo_evento", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="PENDENTE"
        ),
        sa.Column(
            "criado_em", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("processado_em", sa.DateTime(), nullable=True),
        sa.Column("erro", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("outbox_eventos")
