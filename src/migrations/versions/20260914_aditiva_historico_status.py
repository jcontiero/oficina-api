"""aditiva historico status

Revision ID: 202609140001
Revises: 28c30c8cd20c
Create Date: 2026-09-14 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "202609140001"
down_revision = "28c30c8cd20c"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Adicionar status no cliente
    op.add_column(
        "clientes",
        sa.Column(
            "status", sa.String(length=20), server_default="ATIVO", nullable=False
        ),
    )
    op.add_column(
        "veiculos",
        sa.Column(
            "status", sa.String(length=20), server_default="ATIVO", nullable=False
        ),
    )

    # 2. Criar tabela historico_os
    op.create_table(
        "historico_os",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("os_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status_anterior",
            sa.Enum(
                "RECEBIDA",
                "EM_DIAGNOSTICO",
                "AGUARDANDO_ORCAMENTO",
                "AGUARDANDO_APROVACAO",
                "EM_EXECUCAO",
                "SERVICOS_CONCLUIDOS",
                "FINALIZADA",
                "ENTREGUE",
                "CANCELADA",
                name="status_os",
            ),
            nullable=True,
        ),
        sa.Column(
            "status_novo",
            sa.Enum(
                "RECEBIDA",
                "EM_DIAGNOSTICO",
                "AGUARDANDO_ORCAMENTO",
                "AGUARDANDO_APROVACAO",
                "EM_EXECUCAO",
                "SERVICOS_CONCLUIDOS",
                "FINALIZADA",
                "ENTREGUE",
                "CANCELADA",
                name="status_os",
            ),
            nullable=False,
        ),
        sa.Column("ocorrido_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sequencia", sa.Integer(), nullable=False),
        sa.Column("origem", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["os_id"],
            ["ordens_de_servico.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Backfill conservador para as OS existentes
    op.execute("""
        INSERT INTO historico_os (id, os_id, status_anterior, status_novo, ocorrido_em, sequencia, origem)
        SELECT 
            gen_random_uuid(), 
            id, 
            NULL, 
            status::status_os, 
            criada_em, 
            1, 
            'MIGRACAO'
        FROM ordens_de_servico
    """)


def downgrade():
    op.drop_table("historico_os")
    op.drop_column("clientes", "status")
    op.drop_column("veiculos", "status")
