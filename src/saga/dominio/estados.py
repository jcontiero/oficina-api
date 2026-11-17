from enum import Enum


class EstadoSaga(str, Enum):
    ABERTA = "ABERTA"
    DIAGNOSTICO = "DIAGNOSTICO"
    GERANDO_ORCAMENTO = "GERANDO_ORCAMENTO"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"
    RESERVANDO_PECAS = "RESERVANDO_PECAS"
    CRIANDO_COBRANCA = "CRIANDO_COBRANCA"
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    ENFILEIRANDO = "ENFILEIRANDO"
    EM_EXECUCAO = "EM_EXECUCAO"
    CONCLUIDA = "CONCLUIDA"
    RECUSADA = "RECUSADA"
    COMPENSANDO_BLOQUEIO_EXECUCAO = "COMPENSANDO_BLOQUEIO_EXECUCAO"
    COMPENSANDO_EFEITOS = "COMPENSANDO_EFEITOS"
    COMPENSADA = "COMPENSADA"
    INTERVENCAO_MANUAL = "INTERVENCAO_MANUAL"


class SubestadoCompensacao(str, Enum):
    AGUARDANDO_BARREIRA_EXECUCAO = "AGUARDANDO_BARREIRA_EXECUCAO"
    EXECUTANDO_COMPENSACOES = "EXECUTANDO_COMPENSACOES"
    FINALIZADA = "FINALIZADA"
    BLOQUEADA_POR_REPARO_INICIADO = "BLOQUEADA_POR_REPARO_INICIADO"


class CompensacaoFinanceiraStatus(str, Enum):
    NAO_APLICAVEL = "NAO_APLICAVEL"
    PENDENTE = "PENDENTE"
    CONCLUIDA = "CONCLUIDA"
    FALHA_INTERVENCAO = "FALHA_INTERVENCAO"


class MotivoCompensacao(str, Enum):
    FALHA_ENFILEIRAMENTO = "FALHA_ENFILEIRAMENTO"
    FALHA_COBRANCA = "FALHA_COBRANCA"
    PAGAMENTO_EXPIRADO = "PAGAMENTO_EXPIRADO"
    PAGAMENTO_RECUSADO = "PAGAMENTO_RECUSADO"
    ORCAMENTO_RECUSADO = "ORCAMENTO_RECUSADO"
    ESTOQUE_INSUFICIENTE = "ESTOQUE_INSUFICIENTE"
    TIMEOUT_DIAGNOSTICO = "TIMEOUT_DIAGNOSTICO"
    TIMEOUT_ORCAMENTO = "TIMEOUT_ORCAMENTO"
    PAGAMENTO_TARDIO = "PAGAMENTO_TARDIO"
    CANCELAMENTO_CLIENTE = "CANCELAMENTO_CLIENTE"


TRANSICOES_SAGA_VALIDAS: dict[EstadoSaga, list[EstadoSaga]] = {
    EstadoSaga.ABERTA: [
        EstadoSaga.DIAGNOSTICO,
        EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO,
    ],
    EstadoSaga.DIAGNOSTICO: [
        EstadoSaga.GERANDO_ORCAMENTO,
        EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO,
    ],
    EstadoSaga.GERANDO_ORCAMENTO: [
        EstadoSaga.AGUARDANDO_APROVACAO,
        EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO,
    ],
    EstadoSaga.AGUARDANDO_APROVACAO: [
        EstadoSaga.RESERVANDO_PECAS,
        EstadoSaga.RECUSADA,
        EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO,
    ],
    EstadoSaga.RESERVANDO_PECAS: [
        EstadoSaga.CRIANDO_COBRANCA,
        EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO,
    ],
    EstadoSaga.CRIANDO_COBRANCA: [
        EstadoSaga.AGUARDANDO_PAGAMENTO,
        EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO,
    ],
    EstadoSaga.AGUARDANDO_PAGAMENTO: [
        EstadoSaga.ENFILEIRANDO,
        EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO,
    ],
    EstadoSaga.ENFILEIRANDO: [
        EstadoSaga.EM_EXECUCAO,
        EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO,
    ],
    EstadoSaga.EM_EXECUCAO: [
        EstadoSaga.CONCLUIDA,
        EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO,
        EstadoSaga.INTERVENCAO_MANUAL,
    ],
    EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO: [
        EstadoSaga.COMPENSANDO_EFEITOS,
        EstadoSaga.INTERVENCAO_MANUAL,
    ],
    EstadoSaga.COMPENSANDO_EFEITOS: [
        EstadoSaga.COMPENSADA,
        EstadoSaga.INTERVENCAO_MANUAL,
    ],
    EstadoSaga.CONCLUIDA: [],
    EstadoSaga.RECUSADA: [
        EstadoSaga.COMPENSANDO_BLOQUEIO_EXECUCAO,
    ],
    EstadoSaga.COMPENSADA: [],
    EstadoSaga.INTERVENCAO_MANUAL: [
        EstadoSaga.COMPENSANDO_EFEITOS,
        EstadoSaga.COMPENSADA,
    ],
}


def exige_barreira_execucao(comando_compensacao: str) -> bool:
    """
    Toda compensação de efeitos (liberar reserva, cancelar orçamento, cancelar cobrança
    ou estornar pagamento) exige obrigatoriamente que a barreira CancelarExecucao.v1 ->
    ExecucaoCancelada.v1 já tenha sido confirmada com execucao_cancelada_event_id.
    """
    return comando_compensacao in {
        "LiberarReserva.v1",
        "CancelarOrcamento.v1",
        "CancelarCobranca.v1",
        "EstornarPagamento.v1",
    }
