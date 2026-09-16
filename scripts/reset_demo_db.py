import os
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.config import Configuracoes
from src.identidade.infraestrutura.bcrypt_provider import BcryptHashProvider
from src.identidade.infraestrutura.modelos import UsuarioModel
from src.identidade.dominio.entidades import PerfilUsuario
from src.atendimento.infraestrutura.modelos import (
    ClienteModel,
    VeiculoModel,
    OrdemDeServicoModel,
    ItemServicoModel,
    ItemPecaModel,
)
from src.catalogo.infraestrutura.modelos import ServicoModel
from src.estoque.infraestrutura.modelos import PecaModel
from src.atendimento.dominio.value_objects import StatusOS


def reset_and_seed_demo():
    configuracoes = Configuracoes()
    engine = create_engine(configuracoes.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    hash_provider = BcryptHashProvider()
    db = SessionLocal()

    print("Zerando tabelas operacionais...")
    try:
        db.execute(text("""
            TRUNCATE TABLE 
                outbox_eventos, 
                itens_peca, 
                itens_servico, 
                ordens_de_servico, 
                veiculos, 
                clientes, 
                servicos, 
                pecas, 
                usuarios 
            CASCADE;
        """))
        db.commit()
    except Exception as e:
        print(f"Erro ao truncar (tentando delete): {e}")
        db.rollback()
        for model in [ItemPecaModel, ItemServicoModel, OrdemDeServicoModel, VeiculoModel, ClienteModel, ServicoModel, PecaModel, UsuarioModel]:
            db.query(model).delete()
        db.commit()

    print("Inserindo dados de referência para o vídeo...")

    # 1. Usuários
    admin = UsuarioModel(
        id=uuid4(),
        email="admin@oficina.com.br",
        senha_hash=hash_provider.hash("admin123"),
        perfil=PerfilUsuario.ADMIN,
    )
    mecanico = UsuarioModel(
        id=uuid4(),
        email="mecanico@oficina.com.br",
        senha_hash=hash_provider.hash("senha123"),
        perfil=PerfilUsuario.MECANICO,
    )
    db.add_all([admin, mecanico])

    # 2. Catálogo de Serviços
    s_oleo = ServicoModel(
        id=uuid4(),
        nome="Troca de Óleo e Filtro",
        descricao="Substituição completa do óleo lubrificante sintético 5W30 e filtro de óleo",
        preco_base=Decimal("150.00"),
        tempo_estimado_minutos=60,
    )
    s_freio = ServicoModel(
        id=uuid4(),
        nome="Revisão do Sistema de Freios",
        descricao="Inspeção de pastilhas, discos, fluido e sangria do sistema",
        preco_base=Decimal("220.00"),
        tempo_estimado_minutos=90,
    )
    s_diag = ServicoModel(
        id=uuid4(),
        nome="Diagnóstico Eletrônico Computadorizado",
        descricao="Varredura via scanner OBD-II para leitura e diagnóstico de falhas",
        preco_base=Decimal("180.00"),
        tempo_estimado_minutos=45,
    )
    db.add_all([s_oleo, s_freio, s_diag])

    # 3. Catálogo de Peças (Estoque abastecido)
    p_oleo = PecaModel(
        id=uuid4(),
        nome="Óleo Sintético 5W30 (1L)",
        codigo="OL-5W30-01",
        preco_unitario=Decimal("45.00"),
        quantidade_disponivel=100,
        quantidade_minima_alerta=15,
    )
    p_foleo = PecaModel(
        id=uuid4(),
        nome="Filtro de Óleo Blindado",
        codigo="FO-001",
        preco_unitario=Decimal("35.00"),
        quantidade_disponivel=50,
        quantidade_minima_alerta=10,
    )
    p_past = PecaModel(
        id=uuid4(),
        nome="Jogo de Pastilhas de Freio Dianteiro",
        codigo="PF-002",
        preco_unitario=Decimal("140.00"),
        quantidade_disponivel=30,
        quantidade_minima_alerta=5,
    )
    db.add_all([p_oleo, p_foleo, p_past])

    # 4. Cliente Principal do Vídeo (CPF 12345678909)
    cliente_jonas = ClienteModel(
        id=uuid4(),
        nome="Jonas Contiero",
        cpf="12345678909",
        cnpj=None,
        email="jonas@oficina.com.br",
        telefone="11988887777",
    )
    cliente_maria = ClienteModel(
        id=uuid4(),
        nome="Maria Silva",
        cpf="52998224725",
        cnpj=None,
        email="maria@exemplo.com.br",
        telefone="11977776666",
    )
    db.add_all([cliente_jonas, cliente_maria])

    # 5. Veículo do Jonas
    veiculo_jonas = VeiculoModel(
        id=uuid4(),
        cliente_id=cliente_jonas.id,
        placa="ABC1234",
        marca="Toyota",
        modelo="Corolla XEi",
        ano=2022,
        cor="Prata",
    )
    db.add(veiculo_jonas)
    db.commit()

    # 6. Uma Ordem de Serviço pronta em "AGUARDANDO_APROVACAO" para o cliente poder aprovar no vídeo
    os_demo = OrdemDeServicoModel(
        id=uuid4(),
        cliente_id=cliente_jonas.id,
        veiculo_id=veiculo_jonas.id,
        descricao_problema="Barulho metálico na frenagem dianteira e luz de alerta de serviço no painel.",
        status=StatusOS.AGUARDANDO_APROVACAO,
        valor_orcamento=Decimal("360.00"),
        criada_em=datetime.now(timezone.utc),
        atualizada_em=datetime.now(timezone.utc),
    )
    db.add(os_demo)
    db.commit()

    item_serv = ItemServicoModel(
        id=uuid4(),
        os_id=os_demo.id,
        servico_id=s_freio.id,
        descricao=s_freio.nome,
        preco_unitario=s_freio.preco_base,
    )
    item_peca = ItemPecaModel(
        id=uuid4(),
        os_id=os_demo.id,
        peca_id=p_past.id,
        descricao=p_past.nome,
        quantidade=1,
        preco_unitario=p_past.preco_unitario,
    )
    db.add_all([item_serv, item_peca])
    db.commit()
    os_id_str = str(os_demo.id)
    db.close()

    print(f"Banco reiniciado com sucesso! OS ID para teste: {os_id_str}")


if __name__ == "__main__":
    reset_and_seed_demo()
