from src.shared.aplicacao.unit_of_work import UnitOfWork
from src.shared.infraestrutura.unit_of_work import SQLAlchemyUnitOfWork
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import Configuracoes
from src.identidade.aplicacao.casos_de_uso import AutenticarUsuario, CriarUsuario
from src.identidade.aplicacao.ports import ProvedorHashSenha, ProvedorToken
from src.identidade.infraestrutura.bcrypt_provider import BcryptHashProvider
from src.identidade.infraestrutura.jwt_provider import JwtTokenProvider
from src.identidade.infraestrutura.jwt_cliente_provider import JwtTokenProviderCliente
from src.identidade.infraestrutura.jwt_cliente_provider import JwtTokenProviderCliente
from src.identidade.infraestrutura.jwt_cliente_provider import JwtTokenProviderCliente
from src.identidade.infraestrutura.repositorios import UsuarioRepositorioImpl

from src.atendimento.aplicacao.casos_de_uso import (
    CadastrarCliente,
    ListarClientes,
    BuscarCliente,
    AtualizarCliente,
    RemoverCliente,
    CadastrarVeiculo,
    ListarVeiculos,
    BuscarVeiculo,
    AtualizarVeiculo,
    RemoverVeiculo,
    AbrirOrdemDeServico,
    ListarOrdensDeServico,
    BuscarOrdemDeServico,
    IniciarDiagnostico,
    FinalizarDiagnostico,
    AdicionarServico,
    AdicionarPeca,
    GerarOrcamento,
    AprovarOrcamento,
    RecusarOrcamento,
    ExecutarServico,
    FinalizarOS,
    EntregarVeiculo,
    AbrirOrdemDeServicoUnificada,
    ConsultarStatusOrdemDeServico,
    ProcessarAprovacaoOrcamento,
    ListarOrdensDeServicoAtivas,
    AtualizarStatusViaWebhook,
)
from src.atendimento.aplicacao.ports import Notificador
from src.atendimento.infraestrutura.repositorios import (
    ClienteRepositorioImpl,
    VeiculoRepositorioImpl,
    OrdemDeServicoRepositorioImpl,
)

from src.catalogo.aplicacao.casos_de_uso import (
    CadastrarServico,
    ListarServicos,
    BuscarServico,
    AtualizarServico,
    RemoverServico,
)
from src.catalogo.infraestrutura.repositorios import ServicoRepositorioImpl

from src.estoque.aplicacao.casos_de_uso import (
    CadastrarPeca,
    ListarPecas,
    BuscarPeca,
    AtualizarPeca,
    ReporEstoque,
    RemoverPeca,
)
from src.estoque.aplicacao.ports import NotificadorEstoque
from src.estoque.infraestrutura.repositorios import PecaRepositorioImpl

from src.relatorios.aplicacao.casos_de_uso import GerarRelatorioTempoMedioDeServicos
from src.relatorios.aplicacao.ports import ConsultaRelatorios
from src.relatorios.infraestrutura.consulta_relatorios import RelatorioConsultaImpl

from src.shared.infraestrutura.notificador_smtp import SmtpNotificador


class Container:
    def __init__(self, configuracoes: Configuracoes | None = None) -> None:
        self.config = configuracoes or Configuracoes()  # type: ignore[call-arg]
        self.engine = create_engine(self.config.database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        self.token_provider: ProvedorToken = JwtTokenProvider(self.config)
        self.token_provider_cliente: ProvedorToken = JwtTokenProviderCliente(self.config)
        self.hash_provider: ProvedorHashSenha = BcryptHashProvider()
        self.notificador: Notificador = SmtpNotificador(self.config)
        self.notificador_estoque: NotificadorEstoque = SmtpNotificador(self.config)

    def get_db(self) -> Generator[Session, None, None]:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()


def _get_container(request: Request) -> Container:
    return request.app.state.container


def _get_session(
    container: Container = Depends(_get_container),
) -> Generator[Session, None, None]:
    yield from container.get_db()


DBDep = Annotated[Session, Depends(_get_session)]

def get_uow(db: DBDep) -> UnitOfWork:
    return SQLAlchemyUnitOfWork(db)

UowDep = Annotated[UnitOfWork, Depends(get_uow)]


def get_token_provider(container: Container = Depends(_get_container)) -> ProvedorToken:
    return container.token_provider

def get_token_provider_cliente(container: Container = Depends(_get_container)) -> ProvedorToken:
    return container.token_provider_cliente


def get_hash_provider(
    container: Container = Depends(_get_container),
) -> ProvedorHashSenha:
    return container.hash_provider


def get_notificador(container: Container = Depends(_get_container)) -> Notificador:
    return container.notificador


def get_notificador_estoque(
    container: Container = Depends(_get_container),
) -> NotificadorEstoque:
    return container.notificador_estoque


def get_consulta_relatorios(db: DBDep) -> ConsultaRelatorios:
    return RelatorioConsultaImpl(db)


# -- Identidade ----------------------------------------------------------------


def get_autenticar_usuario(
    db: DBDep,
    token_provider: Annotated[ProvedorToken, Depends(get_token_provider)],
    hash_provider: Annotated[ProvedorHashSenha, Depends(get_hash_provider)],
) -> AutenticarUsuario:
    return AutenticarUsuario(
        repo=UsuarioRepositorioImpl(db),
        token_provider=token_provider,
        hash_provider=hash_provider,
    )


def get_criar_usuario(
    db: DBDep,
    hash_provider: Annotated[ProvedorHashSenha, Depends(get_hash_provider)], uow: UowDep,
) -> CriarUsuario:
    return CriarUsuario(repo=UsuarioRepositorioImpl(db), hash_provider=hash_provider, uow=uow)


# -- Clientes ------------------------------------------------------------------


def get_cadastrar_cliente(db: DBDep, uow: UowDep) -> CadastrarCliente:
    return CadastrarCliente(ClienteRepositorioImpl(db), uow=uow)


def get_listar_clientes(db: DBDep) -> ListarClientes:
    return ListarClientes(ClienteRepositorioImpl(db))


def get_buscar_cliente(db: DBDep) -> BuscarCliente:
    return BuscarCliente(ClienteRepositorioImpl(db))


def get_atualizar_cliente(db: DBDep, uow: UowDep) -> AtualizarCliente:
    return AtualizarCliente(ClienteRepositorioImpl(db), uow=uow)


def get_remover_cliente(db: DBDep, uow: UowDep) -> RemoverCliente:
    return RemoverCliente(
        ClienteRepositorioImpl(db),
        OrdemDeServicoRepositorioImpl(db),
     uow=uow)


# -- Veículos ------------------------------------------------------------------


def get_cadastrar_veiculo(db: DBDep, uow: UowDep) -> CadastrarVeiculo:
    return CadastrarVeiculo(
        VeiculoRepositorioImpl(db),
        ClienteRepositorioImpl(db),
     uow=uow)


def get_listar_veiculos(db: DBDep) -> ListarVeiculos:
    return ListarVeiculos(VeiculoRepositorioImpl(db))


def get_buscar_veiculo(db: DBDep) -> BuscarVeiculo:
    return BuscarVeiculo(VeiculoRepositorioImpl(db))


def get_atualizar_veiculo(db: DBDep, uow: UowDep) -> AtualizarVeiculo:
    return AtualizarVeiculo(VeiculoRepositorioImpl(db), uow=uow)


def get_remover_veiculo(db: DBDep, uow: UowDep) -> RemoverVeiculo:
    return RemoverVeiculo(
        VeiculoRepositorioImpl(db),
        OrdemDeServicoRepositorioImpl(db),
     uow=uow)


# -- Ordens de Serviço ---------------------------------------------------------


def get_abrir_ordem_de_servico(db: DBDep, uow: UowDep) -> AbrirOrdemDeServico:
    return AbrirOrdemDeServico(
        OrdemDeServicoRepositorioImpl(db),
        ClienteRepositorioImpl(db),
        VeiculoRepositorioImpl(db),
     uow=uow)


def get_listar_ordens_de_servico(db: DBDep) -> ListarOrdensDeServico:
    return ListarOrdensDeServico(OrdemDeServicoRepositorioImpl(db))


def get_buscar_ordem_de_servico(db: DBDep) -> BuscarOrdemDeServico:
    return BuscarOrdemDeServico(OrdemDeServicoRepositorioImpl(db))


def get_iniciar_diagnostico(db: DBDep, uow: UowDep) -> IniciarDiagnostico:
    return IniciarDiagnostico(OrdemDeServicoRepositorioImpl(db), uow=uow)


def get_finalizar_diagnostico(
    db: DBDep,
    notificador: Annotated[Notificador, Depends(get_notificador)], uow: UowDep,
) -> FinalizarDiagnostico:
    return FinalizarDiagnostico(
        OrdemDeServicoRepositorioImpl(db),
        VeiculoRepositorioImpl(db),
        ClienteRepositorioImpl(db),
        notificador,
     uow=uow)


def get_adicionar_servico(db: DBDep, uow: UowDep) -> AdicionarServico:
    return AdicionarServico(
        OrdemDeServicoRepositorioImpl(db),
        ServicoRepositorioImpl(db),
     uow=uow)


def get_adicionar_peca(db: DBDep, uow: UowDep) -> AdicionarPeca:
    return AdicionarPeca(
        OrdemDeServicoRepositorioImpl(db),
        PecaRepositorioImpl(db),
     uow=uow)


def get_gerar_orcamento(
    db: DBDep,
    notificador: Annotated[Notificador, Depends(get_notificador)], uow: UowDep,
) -> GerarOrcamento:
    return GerarOrcamento(
        OrdemDeServicoRepositorioImpl(db),
        ClienteRepositorioImpl(db),
        VeiculoRepositorioImpl(db),
        notificador,
     uow=uow)


def get_aprovar_orcamento(db: DBDep, uow: UowDep) -> AprovarOrcamento:
    return AprovarOrcamento(
        OrdemDeServicoRepositorioImpl(db),
        PecaRepositorioImpl(db),
     uow=uow)


def get_recusar_orcamento(
    db: DBDep,
    notificador: Annotated[Notificador, Depends(get_notificador)], uow: UowDep,
) -> RecusarOrcamento:
    return RecusarOrcamento(
        OrdemDeServicoRepositorioImpl(db),
        ClienteRepositorioImpl(db),
        VeiculoRepositorioImpl(db),
        notificador,
     uow=uow)


def get_executar_servico(
    db: DBDep,
    notificador: Annotated[Notificador, Depends(get_notificador)], uow: UowDep,
) -> ExecutarServico:
    return ExecutarServico(
        OrdemDeServicoRepositorioImpl(db),
        VeiculoRepositorioImpl(db),
        notificador,
     uow=uow)


def get_finalizar_os(
    db: DBDep,
    notificador: Annotated[Notificador, Depends(get_notificador)], uow: UowDep,
) -> FinalizarOS:
    return FinalizarOS(
        OrdemDeServicoRepositorioImpl(db),
        ClienteRepositorioImpl(db),
        VeiculoRepositorioImpl(db),
        notificador,
     uow=uow)


def get_entregar_veiculo(db: DBDep, uow: UowDep) -> EntregarVeiculo:
    return EntregarVeiculo(OrdemDeServicoRepositorioImpl(db), uow=uow)


def get_abrir_ordem_de_servico_unificada(db: DBDep, uow: UowDep) -> AbrirOrdemDeServicoUnificada:
    return AbrirOrdemDeServicoUnificada(
        OrdemDeServicoRepositorioImpl(db),
        ClienteRepositorioImpl(db),
        VeiculoRepositorioImpl(db),
        ServicoRepositorioImpl(db),
        PecaRepositorioImpl(db),
     uow=uow)


def get_consultar_status_ordem_de_servico(
    db: DBDep,
) -> ConsultarStatusOrdemDeServico:
    return ConsultarStatusOrdemDeServico(OrdemDeServicoRepositorioImpl(db))


def get_processar_aprovacao_orcamento(
    db: DBDep,
    uow: UowDep,
) -> ProcessarAprovacaoOrcamento:
    return ProcessarAprovacaoOrcamento(
        OrdemDeServicoRepositorioImpl(db),
        PecaRepositorioImpl(db),
     uow=uow)


def get_listar_ordens_de_servico_ativas(
    db: DBDep,
) -> ListarOrdensDeServicoAtivas:
    return ListarOrdensDeServicoAtivas(OrdemDeServicoRepositorioImpl(db))


def get_atualizar_status_via_webhook(
    db: DBDep,
    token_provider: Annotated[ProvedorToken, Depends(get_token_provider)], uow: UowDep,
) -> AtualizarStatusViaWebhook:
    return AtualizarStatusViaWebhook(
        OrdemDeServicoRepositorioImpl(db),
        token_provider,
     uow=uow)


# -- Catálogo ------------------------------------------------------------------


def get_cadastrar_servico(db: DBDep, uow: UowDep) -> CadastrarServico:
    return CadastrarServico(ServicoRepositorioImpl(db), uow=uow)


def get_listar_servicos(db: DBDep) -> ListarServicos:
    return ListarServicos(ServicoRepositorioImpl(db))


def get_buscar_servico(db: DBDep) -> BuscarServico:
    return BuscarServico(ServicoRepositorioImpl(db))


def get_atualizar_servico(db: DBDep, uow: UowDep) -> AtualizarServico:
    return AtualizarServico(ServicoRepositorioImpl(db), uow=uow)


def get_remover_servico(db: DBDep, uow: UowDep) -> RemoverServico:
    return RemoverServico(ServicoRepositorioImpl(db), uow=uow)


# -- Estoque -------------------------------------------------------------------


def get_cadastrar_peca(db: DBDep, uow: UowDep) -> CadastrarPeca:
    return CadastrarPeca(PecaRepositorioImpl(db), uow=uow)


def get_listar_pecas(db: DBDep) -> ListarPecas:
    return ListarPecas(PecaRepositorioImpl(db))


def get_buscar_peca(db: DBDep) -> BuscarPeca:
    return BuscarPeca(PecaRepositorioImpl(db))


def get_atualizar_peca(db: DBDep, uow: UowDep) -> AtualizarPeca:
    return AtualizarPeca(PecaRepositorioImpl(db), uow=uow)


def get_repor_estoque(
    db: DBDep,
    notificador: Annotated[NotificadorEstoque, Depends(get_notificador_estoque)], uow: UowDep,
) -> ReporEstoque:
    return ReporEstoque(PecaRepositorioImpl(db), notificador, uow=uow)


def get_remover_peca(db: DBDep, uow: UowDep) -> RemoverPeca:
    return RemoverPeca(PecaRepositorioImpl(db), uow=uow)


# -- Relatórios ----------------------------------------------------------------


def get_gerar_relatorio_tempo_medio(
    consulta: Annotated[ConsultaRelatorios, Depends(get_consulta_relatorios)],
) -> GerarRelatorioTempoMedioDeServicos:
    return GerarRelatorioTempoMedioDeServicos(consulta)
