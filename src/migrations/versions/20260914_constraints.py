"""constraints fase 3

Revision ID: 202609140002
Revises: 202609140001
Create Date: 2026-09-14 18:05:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '202609140002'
down_revision = '202609140001'
branch_labels = None
depends_on = None

def upgrade():
    # Constraints
    op.create_check_constraint('ck_cliente_doc', 'clientes', '(cpf IS NOT NULL AND cnpj IS NULL) OR (cpf IS NULL AND cnpj IS NOT NULL)')
    op.create_check_constraint('ck_item_peca_qtd', 'itens_peca', 'quantidade > 0')
    op.create_check_constraint('ck_pecas_estoque', 'pecas', 'quantidade_disponivel >= 0')
    op.create_check_constraint('ck_item_servico_preco', 'itens_servico', 'preco_unitario >= 0')
    op.create_check_constraint('ck_item_peca_preco', 'itens_peca', 'preco_unitario >= 0')
    op.create_check_constraint('ck_servico_preco', 'servicos', 'preco_base >= 0')
    op.create_check_constraint('ck_peca_preco', 'pecas', 'preco_unitario >= 0')

    # Indices
    op.create_index('ix_historico_os_os_id_ocorrido', 'historico_os', ['os_id', 'ocorrido_em'])
    op.create_index('ix_os_cliente_id', 'ordens_de_servico', ['cliente_id'])
    op.create_index('ix_os_veiculo_id', 'ordens_de_servico', ['veiculo_id'])
    op.create_index('ix_os_status', 'ordens_de_servico', ['status'])
    op.create_index('ix_os_criada_em', 'ordens_de_servico', ['criada_em'])
    op.create_index('ix_os_status_criada_em', 'ordens_de_servico', ['status', 'criada_em'])


def downgrade():
    op.drop_index('ix_os_status_criada_em', 'ordens_de_servico')
    op.drop_index('ix_os_criada_em', 'ordens_de_servico')
    op.drop_index('ix_os_status', 'ordens_de_servico')
    op.drop_index('ix_os_veiculo_id', 'ordens_de_servico')
    op.drop_index('ix_os_cliente_id', 'ordens_de_servico')
    op.drop_index('ix_historico_os_os_id_ocorrido', 'historico_os')

    op.drop_constraint('ck_peca_preco', 'pecas', type_='check')
    op.drop_constraint('ck_servico_preco', 'servicos', type_='check')
    op.drop_constraint('ck_item_peca_preco', 'itens_peca', type_='check')
    op.drop_constraint('ck_item_servico_preco', 'itens_servico', type_='check')
    op.drop_constraint('ck_pecas_estoque', 'pecas', type_='check')
    op.drop_constraint('ck_item_peca_qtd', 'itens_peca', type_='check')
    op.drop_constraint('ck_cliente_doc', 'clientes', type_='check')
