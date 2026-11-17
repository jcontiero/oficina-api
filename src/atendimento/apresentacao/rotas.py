from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from src.identidade.dominio.entidades import Principal

from src.shared.dependencias import get_usuario_atual, require_admin, require_mecanico
from src.container import (
    DBDep,
    get_abrir_ordem_de_servico,
    get_cadastrar_cliente,
    get_listar_clientes,
    get_buscar_cliente,
    get_atualizar_cliente,
    get_remover_cliente,
    get_cadastrar_veiculo,
    get_listar_veiculos,
    get_buscar_veiculo,
    get_atualizar_veiculo,
    get_remover_veiculo,
    get_buscar_ordem_de_servico,
    get_iniciar_diagnostico,
    get_finalizar_diagnostico,
    get_adicionar_servico,
    get_adicionar_peca,
    get_gerar_orcamento,
    get_executar_servico,
    get_finalizar_os,
    get_entregar_veiculo,
    get_abrir_ordem_de_servico_unificada,
    get_consultar_status_ordem_de_servico,
    get_processar_aprovacao_orcamento,
    get_listar_ordens_de_servico_ativas,
    get_atualizar_status_via_webhook,
)
from src.estoque.dominio.excecoes import (
    EstoqueInsuficienteError,
    PecaNaoEncontradaError,
)
from src.catalogo.dominio.excecoes import ServicoNaoEncontradoError
from src.atendimento.aplicacao.casos_de_uso import (
    AbrirOrdemDeServico,
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
    BuscarOrdemDeServico,
    IniciarDiagnostico,
    FinalizarDiagnostico,
    AdicionarServico,
    AdicionarPeca,
    GerarOrcamento,
    ExecutarServico,
    FinalizarOS,
    EntregarVeiculo,
    AbrirOrdemDeServicoUnificada,
    ConsultarStatusOrdemDeServico,
    ProcessarAprovacaoOrcamento,
    ListarOrdensDeServicoAtivas,
    AtualizarStatusViaWebhook,
)
from src.atendimento.dominio.excecoes import (
    ClienteNaoEncontradoError,
    VeiculoNaoEncontradoError,
    VeiculoComOsAtivaError,
    ClienteComOsAtivaError,
    DocumentoDuplicadoError,
    PlacaDuplicadaError,
    TransicaoInvalidaError,
    TransicaoDeStatusInvalidaError,
    OsSemServicosError,
    ItemNaoEncontradoError,
    OrdemDeServicoNaoEncontradaError,
    TokenDeAprovacaoInvalidoError,
    TokenDeAprovacaoExpiradoError,
)
from src.atendimento.apresentacao.schemas import (
    CadastrarClienteRequest,
    AtualizarClienteRequest,
    ClienteResponse,
    CadastrarVeiculoRequest,
    AtualizarVeiculoRequest,
    VeiculoResponse,
    AbrirOsRequest,
    FinalizarDiagnosticoRequest,
    AdicionarServicoRequest,
    AdicionarPecaRequest,
    OsResponse,
    AcompanharOsResponse,
    ItensOsResponse,
    StatusOsResponse,
    AprovacaoOrcamentoRequest,
    ListarOsFase2Response,
    WebhookAtualizarStatusRequest,
)
from src.atendimento.dominio.value_objects import (
    para_status_interno,
)

AuthDep = Annotated[Principal, Depends(get_usuario_atual)]
AdminDep = Annotated[Principal, Depends(require_admin)]
MecanicoDep = Annotated[Principal, Depends(require_mecanico)]

router = APIRouter(tags=["Atendimento"])


def _bloquear_se_distribuido(request: Request, servico_dono: str) -> None:
    if not request.app.state.container.config.enable_legacy_monolith_domains:
        raise HTTPException(
            status_code=410,
            detail=(
                f"Operação extraída na Fase 4: o serviço dono exclusivo é {servico_dono}. "
                "O OS Service não executa escrita direta em orçamento, estoque ou execução."
            ),
        )


# -- Clientes ------------------------------------------------------------------


@router.post("/clientes", response_model=ClienteResponse, status_code=201)
def cadastrar_cliente(
    body: CadastrarClienteRequest,
    caso_de_uso: Annotated[CadastrarCliente, Depends(get_cadastrar_cliente)],
    _: MecanicoDep,
):
    try:
        cliente = caso_de_uso.executar(**body.model_dump(exclude={"status"}))
        return ClienteResponse.from_domain(cliente)
    except (ValueError, DocumentoDuplicadoError) as e:
        raise HTTPException(409 if "cadastrado" in str(e) else 400, str(e))


@router.get("/clientes", response_model=list[ClienteResponse])
def listar_clientes(
    caso_de_uso: Annotated[ListarClientes, Depends(get_listar_clientes)],
    _: MecanicoDep,
    busca: str | None = None,
):
    clientes = caso_de_uso.executar(busca)
    return [ClienteResponse.from_domain(c) for c in clientes]


@router.get("/clientes/{id}", response_model=ClienteResponse)
def buscar_cliente(
    id: UUID,
    caso_de_uso: Annotated[BuscarCliente, Depends(get_buscar_cliente)],
    _: MecanicoDep,
):
    try:
        return ClienteResponse.from_domain(caso_de_uso.executar(id))
    except ClienteNaoEncontradoError as e:
        raise HTTPException(404, str(e))


@router.put("/clientes/{id}", response_model=ClienteResponse)
def atualizar_cliente(
    id: UUID,
    body: AtualizarClienteRequest,
    caso_de_uso: Annotated[AtualizarCliente, Depends(get_atualizar_cliente)],
    _: MecanicoDep,
):
    try:
        cliente = caso_de_uso.executar(
            id=id, **body.model_dump(exclude_none=True, exclude={"status"})
        )
        return ClienteResponse.from_domain(cliente)
    except ClienteNaoEncontradoError as e:
        raise HTTPException(404, str(e))


@router.delete("/clientes/{id}", status_code=204)
def remover_cliente(
    id: UUID,
    caso_de_uso: Annotated[RemoverCliente, Depends(get_remover_cliente)],
    _: AdminDep,
):
    try:
        caso_de_uso.executar(id)
    except ClienteNaoEncontradoError as e:
        raise HTTPException(404, str(e))
    except ClienteComOsAtivaError as e:
        raise HTTPException(422, str(e))


# -- Veículos ------------------------------------------------------------------


@router.post("/veiculos", response_model=VeiculoResponse, status_code=201)
def cadastrar_veiculo(
    body: CadastrarVeiculoRequest,
    caso_de_uso: Annotated[CadastrarVeiculo, Depends(get_cadastrar_veiculo)],
    _: MecanicoDep,
):
    try:
        veiculo = caso_de_uso.executar(
            cliente_id=UUID(body.cliente_id),
            placa=body.placa,
            marca=body.marca,
            modelo=body.modelo,
            ano=body.ano,
            cor=body.cor,
        )
        return VeiculoResponse.from_domain(veiculo)
    except ClienteNaoEncontradoError as e:
        raise HTTPException(404, str(e))
    except (PlacaDuplicadaError, ValueError) as e:
        raise HTTPException(409 if "cadastrada" in str(e) else 400, str(e))


@router.get("/veiculos", response_model=list[VeiculoResponse])
def listar_veiculos(
    caso_de_uso: Annotated[ListarVeiculos, Depends(get_listar_veiculos)],
    _: MecanicoDep,
    cliente_id: UUID | None = None,
):
    veiculos = caso_de_uso.executar(cliente_id)
    return [VeiculoResponse.from_domain(v) for v in veiculos]


@router.get("/veiculos/{id}", response_model=VeiculoResponse)
def buscar_veiculo(
    id: UUID,
    caso_de_uso: Annotated[BuscarVeiculo, Depends(get_buscar_veiculo)],
    _: MecanicoDep,
):
    try:
        return VeiculoResponse.from_domain(caso_de_uso.executar(id))
    except VeiculoNaoEncontradoError as e:
        raise HTTPException(404, str(e))


@router.put("/veiculos/{id}", response_model=VeiculoResponse)
def atualizar_veiculo(
    id: UUID,
    body: AtualizarVeiculoRequest,
    caso_de_uso: Annotated[AtualizarVeiculo, Depends(get_atualizar_veiculo)],
    _: MecanicoDep,
):
    try:
        v = caso_de_uso.executar(id=id, **body.model_dump(exclude_none=True))
        return VeiculoResponse.from_domain(v)
    except VeiculoNaoEncontradoError as e:
        raise HTTPException(404, str(e))


@router.delete("/veiculos/{id}", status_code=204)
def remover_veiculo(
    id: UUID,
    caso_de_uso: Annotated[RemoverVeiculo, Depends(get_remover_veiculo)],
    _: AdminDep,
):
    try:
        caso_de_uso.executar(id)
    except VeiculoNaoEncontradoError as e:
        raise HTTPException(404, str(e))
    except VeiculoComOsAtivaError as e:
        raise HTTPException(422, str(e))


# -- Ordens de Serviço ---------------------------------------------------------


@router.post("/ordens-de-servico", response_model=OsResponse, status_code=201)
def abrir_os_unificado(
    request: Request,
    body: AbrirOsRequest,
    caso_de_uso: Annotated[
        AbrirOrdemDeServicoUnificada, Depends(get_abrir_ordem_de_servico_unificada)
    ],
    _: AdminDep,
):
    _bloquear_se_distribuido(
        request, "POST /v1/ordens-servico + oficina-billing/oficina-execucao"
    )
    try:
        os = caso_de_uso.executar(
            cliente_dados=body.cliente.model_dump(),
            veiculo_dados=body.veiculo.model_dump(),
            servicos=[s.model_dump() for s in body.servicos],
            pecas=[p.model_dump() for p in body.pecas],
        )
        return OsResponse.from_domain(os)
    except (ClienteNaoEncontradoError, VeiculoNaoEncontradoError) as e:
        raise HTTPException(404, str(e))
    except (
        VeiculoComOsAtivaError,
        OsSemServicosError,
        ValueError,
    ) as e:
        raise HTTPException(422, str(e))


@router.get("/ordens-de-servico", response_model=list[ListarOsFase2Response])
def listar_os_fase2(
    caso_de_uso: Annotated[
        ListarOrdensDeServicoAtivas, Depends(get_listar_ordens_de_servico_ativas)
    ],
    principal: AuthDep,
):
    from src.identidade.dominio.entidades import ActorType

    cliente_id = principal.id if principal.actor_type == ActorType.CLIENTE else None
    ordens = caso_de_uso.executar(cliente_id=cliente_id)
    return [ListarOsFase2Response.from_domain(o) for o in ordens]


@router.get("/ordens-de-servico/{id}", response_model=OsResponse)
def buscar_os(
    id: UUID,
    caso_de_uso: Annotated[BuscarOrdemDeServico, Depends(get_buscar_ordem_de_servico)],
    principal: AuthDep,
):
    try:
        from src.identidade.dominio.entidades import ActorType

        cliente_id = principal.id if principal.actor_type == ActorType.CLIENTE else None

        return OsResponse.from_domain(caso_de_uso.executar(id, cliente_id=cliente_id))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.get("/ordens-de-servico/{id}/status", response_model=StatusOsResponse)
def consultar_status_os(
    id: UUID,
    caso_de_uso: Annotated[
        ConsultarStatusOrdemDeServico, Depends(get_consultar_status_ordem_de_servico)
    ],
):
    try:
        os, status = caso_de_uso.executar(id)
        return StatusOsResponse(id=str(os.id), status=status)
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.post("/ordens-de-servico/{id}/aprovacao", response_model=OsResponse)
def aprovar_os_fase2(
    request: Request,
    id: UUID,
    body: AprovacaoOrcamentoRequest,
    caso_de_uso: Annotated[
        ProcessarAprovacaoOrcamento, Depends(get_processar_aprovacao_orcamento)
    ],
    principal: AuthDep,
):
    _bloquear_se_distribuido(
        request, "oficina-billing (POST /v1/orcamentos/{id}/decisao)"
    )
    try:
        from src.identidade.dominio.entidades import ActorType
        from fastapi import HTTPException

        if (
            principal.actor_type == ActorType.FUNCIONARIO
            and principal.perfil != "ADMIN"
        ):
            raise HTTPException(403, "Acesso restrito")

        cliente_id = principal.id if principal.actor_type == ActorType.CLIENTE else None
        os = caso_de_uso.executar(id, body.aprovado, body.motivo, cliente_id=cliente_id)
        return OsResponse.from_domain(os)
    except (
        TransicaoInvalidaError,
        TransicaoDeStatusInvalidaError,
        OsSemServicosError,
    ) as e:
        raise HTTPException(422, str(e))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.post("/webhooks/os/{id}/atualizar-status", response_model=OsResponse)
def atualizar_status_via_webhook(
    request: Request,
    id: UUID,
    body: WebhookAtualizarStatusRequest,
    caso_de_uso: Annotated[
        AtualizarStatusViaWebhook, Depends(get_atualizar_status_via_webhook)
    ],
):
    _bloquear_se_distribuido(request, "oficina-billing (POST /webhooks/mercadopago)")
    try:
        novo_status = para_status_interno(body.status)
        os = caso_de_uso.executar(id, body.token, novo_status)
        return OsResponse.from_domain(os)
    except (KeyError, ValueError):
        raise HTTPException(400, f"Status inválido: {body.status}")
    except (
        TransicaoInvalidaError,
        TransicaoDeStatusInvalidaError,
    ) as e:
        raise HTTPException(422, str(e))
    except (
        TokenDeAprovacaoInvalidoError,
        TokenDeAprovacaoExpiradoError,
    ) as e:
        raise HTTPException(401, str(e))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.get("/ordens-de-servico/{id}/itens", response_model=ItensOsResponse)
def listar_itens_os(
    id: UUID,
    caso_buscar: Annotated[BuscarOrdemDeServico, Depends(get_buscar_ordem_de_servico)],
    _: MecanicoDep,
    pendentes: bool = False,
):
    try:
        os = caso_buscar.executar(id)
        return ItensOsResponse.from_domain(os, apenas_pendentes=pendentes)
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.get("/ordens-de-servico/{id}/acompanhar", response_model=AcompanharOsResponse)
def acompanhar_os(
    id: UUID,
    caso_de_uso: Annotated[BuscarOrdemDeServico, Depends(get_buscar_ordem_de_servico)],
):
    try:
        os = caso_de_uso.executar(id)
        return AcompanharOsResponse.from_domain(os)
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.post("/ordens-de-servico/{id}/iniciar-diagnostico", response_model=OsResponse)
def iniciar_diagnostico(
    request: Request,
    id: UUID,
    caso_de_uso: Annotated[IniciarDiagnostico, Depends(get_iniciar_diagnostico)],
    _: MecanicoDep,
):
    _bloquear_se_distribuido(
        request, "oficina-execucao (POST /v1/execucoes/{id}/diagnostico)"
    )
    try:
        return OsResponse.from_domain(caso_de_uso.executar(id))
    except TransicaoInvalidaError as e:
        raise HTTPException(422, str(e))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.post("/ordens-de-servico/{id}/finalizar-diagnostico", response_model=OsResponse)
def finalizar_diagnostico(
    request: Request,
    id: UUID,
    caso_de_uso: Annotated[FinalizarDiagnostico, Depends(get_finalizar_diagnostico)],
    _: MecanicoDep,
    body: FinalizarDiagnosticoRequest | None = None,
):
    _bloquear_se_distribuido(
        request, "oficina-execucao (POST /v1/execucoes/{id}/diagnostico)"
    )
    try:
        laudo = body.laudo_diagnostico if body else None
        return OsResponse.from_domain(caso_de_uso.executar(id, laudo))
    except TransicaoInvalidaError as e:
        raise HTTPException(422, str(e))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.post("/ordens-de-servico/{id}/adicionar-servico", response_model=OsResponse)
def adicionar_servico(
    request: Request,
    id: UUID,
    body: AdicionarServicoRequest,
    caso_de_uso: Annotated[AdicionarServico, Depends(get_adicionar_servico)],
    _: AdminDep,
):
    _bloquear_se_distribuido(request, "oficina-execucao")
    try:
        os = caso_de_uso.executar(id, UUID(body.servico_id), body.observacao)
        return OsResponse.from_domain(os)
    except ServicoNaoEncontradoError as e:
        raise HTTPException(404, str(e))
    except TransicaoInvalidaError as e:
        raise HTTPException(422, str(e))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.post("/ordens-de-servico/{id}/adicionar-peca", response_model=OsResponse)
def adicionar_peca(
    request: Request,
    id: UUID,
    body: AdicionarPecaRequest,
    caso_de_uso: Annotated[AdicionarPeca, Depends(get_adicionar_peca)],
    _: AdminDep,
):
    _bloquear_se_distribuido(request, "oficina-execucao")
    try:
        os = caso_de_uso.executar(id, UUID(body.peca_id), body.quantidade)
        return OsResponse.from_domain(os)
    except TransicaoInvalidaError as e:
        raise HTTPException(422, str(e))
    except EstoqueInsuficienteError as e:
        raise HTTPException(422, str(e))
    except PecaNaoEncontradaError as e:
        raise HTTPException(404, str(e))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.post("/ordens-de-servico/{id}/gerar-orcamento", response_model=OsResponse)
def gerar_orcamento(
    request: Request,
    id: UUID,
    caso_de_uso: Annotated[GerarOrcamento, Depends(get_gerar_orcamento)],
    _: AdminDep,
):
    _bloquear_se_distribuido(request, "oficina-billing")
    try:
        return OsResponse.from_domain(caso_de_uso.executar(id))
    except (TransicaoInvalidaError, OsSemServicosError) as e:
        raise HTTPException(422, str(e))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.post(
    "/ordens-de-servico/{id}/executar-servico/{item_id}", response_model=OsResponse
)
def executar_servico(
    request: Request,
    id: UUID,
    item_id: UUID,
    caso_de_uso: Annotated[ExecutarServico, Depends(get_executar_servico)],
    _: MecanicoDep,
):
    _bloquear_se_distribuido(
        request, "oficina-execucao (POST /v1/execucoes/{id}/iniciar|concluir)"
    )
    try:
        return OsResponse.from_domain(caso_de_uso.executar(id, item_id))
    except (TransicaoInvalidaError, ItemNaoEncontradoError) as e:
        raise HTTPException(422, str(e))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.post("/ordens-de-servico/{id}/finalizar", response_model=OsResponse)
def finalizar_os(
    id: UUID,
    caso_de_uso: Annotated[FinalizarOS, Depends(get_finalizar_os)],
    _: AdminDep,
):
    try:
        return OsResponse.from_domain(caso_de_uso.executar(id))
    except TransicaoInvalidaError as e:
        raise HTTPException(422, str(e))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


@router.post("/ordens-de-servico/{id}/entregar", response_model=OsResponse)
def entregar_veiculo(
    id: UUID,
    caso_de_uso: Annotated[EntregarVeiculo, Depends(get_entregar_veiculo)],
    _: AdminDep,
):
    try:
        return OsResponse.from_domain(caso_de_uso.executar(id))
    except TransicaoInvalidaError as e:
        raise HTTPException(422, str(e))
    except OrdemDeServicoNaoEncontradaError as e:
        raise HTTPException(404, str(e))


# -- Rotas Canônicas Fase 4 (/v1/ordens-servico) -------------------------------


class AbrirOsV1Request(BaseModel):
    cliente_documento: str
    veiculo_placa: str
    descricao_problema: str


@router.post("/v1/ordens-servico", status_code=status.HTTP_202_ACCEPTED)
def abrir_os_v1(
    body: AbrirOsV1Request,
    request: Request,
    response: Response,
    db: DBDep,
    caso_de_uso: Annotated[AbrirOrdemDeServico, Depends(get_abrir_ordem_de_servico)],
    _: AdminDep,
):
    """
    Contrato v1 da Fase 4: cria a OS no estado RECEBIDA, inicia a instância da Saga
    e grava SolicitarDiagnostico.v1 na Outbox dentro da mesma transação SQL, sem
    calcular orçamento nem reservar peças localmente no OS Service.
    """
    from src.saga.aplicacao.orquestrador import OrquestradorSaga

    try:
        os_ent = caso_de_uso.executar(
            cliente_cpf_cnpj=body.cliente_documento,
            veiculo_placa=body.veiculo_placa,
            descricao_problema=body.descricao_problema,
        )
    except (ClienteNaoEncontradoError, VeiculoNaoEncontradoError) as e:
        raise HTTPException(404, str(e))
    except (VeiculoComOsAtivaError, ValueError) as e:
        raise HTTPException(422, str(e))

    env = request.app.state.container.config.environment
    saga = OrquestradorSaga(db, environment=env).iniciar_saga_abertura(
        os_id=os_ent.id,
        cliente_id=os_ent.cliente_id,
        veiculo_id=os_ent.veiculo_id,
        descricao_problema=os_ent.descricao_problema,
        traceparent=request.headers.get("traceparent"),
    )
    db.commit()

    response.headers["Location"] = f"/v1/ordens-servico/{os_ent.id}"
    return {
        "os_id": str(os_ent.id),
        "saga_id": str(saga.id),
        "status": os_ent.status.value,
        "estado_saga": saga.estado,
        "location": f"/v1/ordens-servico/{os_ent.id}",
    }


@router.get("/v1/ordens-servico/{id}/saga")
def consultar_saga_os_v1(
    id: UUID,
    db: DBDep,
    _: AuthDep,
):
    from src.saga.infraestrutura.modelos import SagaInstanceModel

    saga = (
        db.query(SagaInstanceModel)
        .filter(SagaInstanceModel.os_id == str(id))
        .order_by(SagaInstanceModel.rodada.desc())
        .first()
    )
    if saga is None:
        raise HTTPException(404, "Saga não encontrada para esta OS")
    return {
        "saga_id": saga.id,
        "os_id": saga.os_id,
        "rodada": saga.rodada,
        "estado": saga.estado,
        "subestado_compensacao": saga.subestado_compensacao,
        "compensacao_financeira_status": saga.compensacao_financeira_status,
        "execucao_cancelada_event_id": saga.execucao_cancelada_event_id,
        "orcamento_id": saga.orcamento_id,
        "pagamento_id": saga.pagamento_id,
        "total_centavos": saga.total_centavos,
        "efeitos_esperados": saga.efeitos_esperados_json,
        "efeitos_confirmados": saga.efeitos_confirmados_json,
        "version": saga.version,
    }


@router.post("/v1/ordens-servico/{id}/cancelar", status_code=202)
def cancelar_os_via_saga_v1(
    id: UUID,
    request: Request,
    db: DBDep,
    _: AuthDep,
):
    from src.saga.aplicacao.orquestrador import OrquestradorSaga

    env = request.app.state.container.config.environment
    try:
        saga = OrquestradorSaga(db, environment=env).solicitar_cancelamento(
            os_id=id, traceparent=request.headers.get("traceparent")
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "saga_id": saga.id,
        "os_id": saga.os_id,
        "estado": saga.estado,
        "subestado_compensacao": saga.subestado_compensacao,
    }


@router.post("/v1/ordens-servico/{id}/saga/reprocessar-estorno", status_code=202)
def reprocessar_estorno_saga_v1(
    id: UUID,
    request: Request,
    db: DBDep,
    _: AdminDep,
):
    from src.saga.aplicacao.orquestrador import OrquestradorSaga

    env = request.app.state.container.config.environment
    try:
        saga = OrquestradorSaga(db, environment=env).reprocessar_estorno(
            os_id=id, traceparent=request.headers.get("traceparent")
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "saga_id": saga.id,
        "os_id": saga.os_id,
        "estado": saga.estado,
        "compensacao_financeira_status": saga.compensacao_financeira_status,
    }


@router.get("/v1/ordens-servico/{id}", response_model=OsResponse)
def buscar_os_v1(
    id: UUID,
    caso_de_uso: Annotated[BuscarOrdemDeServico, Depends(get_buscar_ordem_de_servico)],
    principal: AuthDep,
):
    return buscar_os(id=id, caso_de_uso=caso_de_uso, principal=principal)


@router.get("/v1/ordens-servico/{id}/historico", response_model=AcompanharOsResponse)
def historico_os_v1(
    id: UUID,
    caso_de_uso: Annotated[BuscarOrdemDeServico, Depends(get_buscar_ordem_de_servico)],
):
    return acompanhar_os(id=id, caso_de_uso=caso_de_uso)


@router.post("/v1/ordens-servico/{id}/entrega", response_model=OsResponse)
def entregar_os_v1(
    id: UUID,
    caso_de_uso: Annotated[EntregarVeiculo, Depends(get_entregar_veiculo)],
    principal: AdminDep,
):
    return entregar_veiculo(id=id, caso_de_uso=caso_de_uso, _=principal)
