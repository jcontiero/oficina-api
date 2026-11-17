"""cria tabela saga_eventos_adiantados para reavaliacao de eventos fora de ordem

Revision ID: 20261117_adiantados
Revises: 20261117_fase4
Create Date: 2026-11-17 14:25:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261117_adiantados"
down_revision = "20261117_fase4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saga_eventos_adiantados",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("saga_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("rodada", sa.Integer(), nullable=False),
        sa.Column("envelope_json", sa.JSON(), nullable=False),
        sa.Column("traceparent", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["saga_id"], ["saga_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_saga_evento_adiantado_event_id"),
    )
    op.create_index(
        "ix_saga_eventos_adiantados_saga_id",
        "saga_eventos_adiantados",
        ["saga_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_saga_eventos_adiantados_saga_id", table_name="saga_eventos_adiantados"
    )
    op.drop_table("saga_eventos_adiantados")
