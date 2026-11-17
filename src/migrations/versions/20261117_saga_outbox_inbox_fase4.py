"""cria tabelas saga_instances, saga_steps, inbox_eventos e evolui outbox_eventos

Revision ID: 20261117_fase4
Revises: 20260914_constraints
Create Date: 2026-11-17 11:15:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20261117_fase4"
down_revision = "c45c34fba153"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for valor in (
                "AGUARDANDO_PAGAMENTO",
                "AGUARDANDO_EXECUCAO",
                "COMPENSACAO_PENDENTE",
            ):
                op.execute(f"ALTER TYPE status_os ADD VALUE IF NOT EXISTS '{valor}'")

    op.create_table(
        "saga_instances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("os_id", sa.String(length=36), nullable=False),
        sa.Column("rodada", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("estado", sa.String(length=40), nullable=False),
        sa.Column("subestado_compensacao", sa.String(length=48), nullable=True),
        sa.Column(
            "compensacao_financeira_status",
            sa.String(length=32),
            nullable=False,
            server_default="NAO_APLICAVEL",
        ),
        sa.Column("execucao_cancelada_event_id", sa.String(length=36), nullable=True),
        sa.Column("compensacao_id", sa.String(length=36), nullable=True),
        sa.Column("motivo_compensacao", sa.String(length=64), nullable=True),
        sa.Column("efeitos_esperados_json", sa.JSON(), nullable=False),
        sa.Column("efeitos_confirmados_json", sa.JSON(), nullable=False),
        sa.Column("orcamento_id", sa.String(length=36), nullable=True),
        sa.Column("orcamento_versao", sa.Integer(), nullable=True),
        sa.Column("pagamento_id", sa.String(length=36), nullable=True),
        sa.Column("total_centavos", sa.Integer(), nullable=True),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_erro", sa.Text(), nullable=True),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizada_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("os_id", "rodada", name="uq_saga_os_rodada"),
    )
    op.create_index("ix_saga_instances_os_id", "saga_instances", ["os_id"])

    op.create_table(
        "saga_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("saga_id", sa.String(length=36), nullable=False),
        sa.Column("etapa", sa.String(length=48), nullable=False),
        sa.Column("comando_event_id", sa.String(length=36), nullable=False),
        sa.Column("comando_tipo", sa.String(length=64), nullable=False),
        sa.Column("resposta_event_id", sa.String(length=36), nullable=True),
        sa.Column("resposta_tipo", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["saga_id"], ["saga_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comando_event_id"),
    )

    op.create_table(
        "inbox_eventos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("consumer", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("saga_id", sa.String(length=36), nullable=True),
        sa.Column("recebido_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("consumer", "event_id", name="uq_inbox_consumer_event"),
    )

    with op.batch_alter_table("outbox_eventos") as batch_op:
        batch_op.add_column(sa.Column("event_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column(
                "topic",
                sa.String(length=128),
                nullable=False,
                server_default="oficina-homolog-eventos-v1",
            )
        )
        batch_op.add_column(
            sa.Column("traceparent", sa.String(length=128), nullable=True)
        )
        batch_op.add_column(
            sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("outbox_eventos") as batch_op:
        batch_op.drop_column("locked_until")
        batch_op.drop_column("next_attempt_at")
        batch_op.drop_column("tentativas")
        batch_op.drop_column("traceparent")
        batch_op.drop_column("topic")
        batch_op.drop_column("event_id")

    op.drop_table("inbox_eventos")
    op.drop_table("saga_steps")
    op.drop_index("ix_saga_instances_os_id", table_name="saga_instances")
    op.drop_table("saga_instances")
