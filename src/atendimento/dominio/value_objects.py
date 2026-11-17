import re
from dataclasses import dataclass
from enum import Enum

REGEX_PLACA = re.compile(r"^[A-Z]{3}[0-9]{4}$|^[A-Z]{3}[0-9][A-Z][0-9]{2}$")

TRANSICOES_VALIDAS: dict


class StatusCliente(str, Enum):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"


class StatusVeiculo(str, Enum):
    ATIVO = "ATIVO"
    INATIVO = "INATIVO"


class StatusOS(str, Enum):
    RECEBIDA = "RECEBIDA"
    EM_DIAGNOSTICO = "EM_DIAGNOSTICO"
    AGUARDANDO_ORCAMENTO = "AGUARDANDO_ORCAMENTO"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    AGUARDANDO_EXECUCAO = "AGUARDANDO_EXECUCAO"
    EM_EXECUCAO = "EM_EXECUCAO"
    SERVICOS_CONCLUIDOS = "SERVICOS_CONCLUIDOS"
    COMPENSACAO_PENDENTE = "COMPENSACAO_PENDENTE"
    FINALIZADA = "FINALIZADA"
    ENTREGUE = "ENTREGUE"
    CANCELADA = "CANCELADA"


class StatusOSFase2(str, Enum):
    RECEBIDA = "Recebida"
    DIAGNOSTICO = "Diagnóstico"
    AGUARDANDO_APROVACAO = "Aguardando Aprovação"
    AGUARDANDO_PAGAMENTO = "Aguardando Pagamento"
    AGUARDANDO_EXECUCAO = "Aguardando Execução"
    EXECUCAO = "Execução"
    COMPENSACAO_PENDENTE = "Compensação Pendente"
    FINALIZADA = "Finalizada"
    ENTREGUE = "Entregue"
    CANCELADA = "Cancelada"


TRANSICOES_VALIDAS = {
    StatusOS.RECEBIDA: [
        StatusOS.EM_DIAGNOSTICO,
        StatusOS.AGUARDANDO_APROVACAO,
        StatusOS.CANCELADA,
    ],
    StatusOS.EM_DIAGNOSTICO: [
        StatusOS.AGUARDANDO_ORCAMENTO,
        StatusOS.AGUARDANDO_APROVACAO,
        StatusOS.COMPENSACAO_PENDENTE,
        StatusOS.CANCELADA,
    ],
    StatusOS.AGUARDANDO_ORCAMENTO: [
        StatusOS.AGUARDANDO_APROVACAO,
        StatusOS.COMPENSACAO_PENDENTE,
        StatusOS.CANCELADA,
    ],
    StatusOS.AGUARDANDO_APROVACAO: [
        StatusOS.AGUARDANDO_PAGAMENTO,
        StatusOS.EM_EXECUCAO,
        StatusOS.EM_DIAGNOSTICO,
        StatusOS.COMPENSACAO_PENDENTE,
        StatusOS.CANCELADA,
    ],
    StatusOS.AGUARDANDO_PAGAMENTO: [
        StatusOS.AGUARDANDO_EXECUCAO,
        StatusOS.EM_EXECUCAO,
        StatusOS.EM_DIAGNOSTICO,
        StatusOS.COMPENSACAO_PENDENTE,
        StatusOS.CANCELADA,
    ],
    StatusOS.AGUARDANDO_EXECUCAO: [
        StatusOS.EM_EXECUCAO,
        StatusOS.COMPENSACAO_PENDENTE,
        StatusOS.CANCELADA,
    ],
    StatusOS.EM_EXECUCAO: [
        StatusOS.SERVICOS_CONCLUIDOS,
        StatusOS.COMPENSACAO_PENDENTE,
    ],
    StatusOS.SERVICOS_CONCLUIDOS: [StatusOS.FINALIZADA],
    StatusOS.COMPENSACAO_PENDENTE: [
        StatusOS.EM_DIAGNOSTICO,
        StatusOS.CANCELADA,
    ],
    StatusOS.FINALIZADA: [StatusOS.ENTREGUE],
    StatusOS.ENTREGUE: [],
    StatusOS.CANCELADA: [],
}


PRIORIDADE_LISTAGEM_FASE2: dict[StatusOSFase2, int] = {
    StatusOSFase2.EXECUCAO: 1,
    StatusOSFase2.AGUARDANDO_EXECUCAO: 2,
    StatusOSFase2.AGUARDANDO_PAGAMENTO: 3,
    StatusOSFase2.AGUARDANDO_APROVACAO: 4,
    StatusOSFase2.DIAGNOSTICO: 5,
    StatusOSFase2.RECEBIDA: 6,
}


def para_status_fase2(status: StatusOS) -> StatusOSFase2:
    mapeamento = {
        StatusOS.RECEBIDA: StatusOSFase2.RECEBIDA,
        StatusOS.EM_DIAGNOSTICO: StatusOSFase2.DIAGNOSTICO,
        StatusOS.AGUARDANDO_ORCAMENTO: StatusOSFase2.AGUARDANDO_APROVACAO,
        StatusOS.AGUARDANDO_APROVACAO: StatusOSFase2.AGUARDANDO_APROVACAO,
        StatusOS.AGUARDANDO_PAGAMENTO: StatusOSFase2.AGUARDANDO_PAGAMENTO,
        StatusOS.AGUARDANDO_EXECUCAO: StatusOSFase2.AGUARDANDO_EXECUCAO,
        StatusOS.EM_EXECUCAO: StatusOSFase2.EXECUCAO,
        StatusOS.SERVICOS_CONCLUIDOS: StatusOSFase2.EXECUCAO,
        StatusOS.COMPENSACAO_PENDENTE: StatusOSFase2.COMPENSACAO_PENDENTE,
        StatusOS.FINALIZADA: StatusOSFase2.FINALIZADA,
        StatusOS.ENTREGUE: StatusOSFase2.ENTREGUE,
        StatusOS.CANCELADA: StatusOSFase2.CANCELADA,
    }
    return mapeamento[status]


def _normalizar_status(texto: str) -> str:
    return (
        texto.upper()
        .replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
        .replace("Ã", "A")
        .replace("Ç", "C")
        .replace(" ", "_")
    )


def para_status_interno(status_fase2: str) -> StatusOS:
    mapeamento = {
        _normalizar_status(StatusOSFase2.RECEBIDA.value): StatusOS.RECEBIDA,
        _normalizar_status(StatusOSFase2.DIAGNOSTICO.value): StatusOS.EM_DIAGNOSTICO,
        _normalizar_status(
            StatusOSFase2.AGUARDANDO_APROVACAO.value
        ): StatusOS.AGUARDANDO_APROVACAO,
        _normalizar_status(
            StatusOSFase2.AGUARDANDO_PAGAMENTO.value
        ): StatusOS.AGUARDANDO_PAGAMENTO,
        _normalizar_status(
            StatusOSFase2.AGUARDANDO_EXECUCAO.value
        ): StatusOS.AGUARDANDO_EXECUCAO,
        _normalizar_status(StatusOSFase2.EXECUCAO.value): StatusOS.EM_EXECUCAO,
        _normalizar_status(
            StatusOSFase2.COMPENSACAO_PENDENTE.value
        ): StatusOS.COMPENSACAO_PENDENTE,
        _normalizar_status(StatusOSFase2.FINALIZADA.value): StatusOS.FINALIZADA,
        _normalizar_status(StatusOSFase2.ENTREGUE.value): StatusOS.ENTREGUE,
        _normalizar_status(StatusOSFase2.CANCELADA.value): StatusOS.CANCELADA,
        "EM_EXECUCAO": StatusOS.EM_EXECUCAO,
        "SERVICOS_CONCLUIDOS": StatusOS.SERVICOS_CONCLUIDOS,
    }
    chave = _normalizar_status(status_fase2)
    if chave in mapeamento:
        return mapeamento[chave]
    return StatusOS(status_fase2)


@dataclass(frozen=True)
class CPF:
    valor: str

    def __post_init__(self):
        limpo = re.sub(r"\D", "", self.valor)
        if not self._valido(limpo):
            raise ValueError(f"CPF inválido: {self.valor}")
        object.__setattr__(self, "valor", limpo)

    def _valido(self, cpf: str) -> bool:
        if len(cpf) != 11 or len(set(cpf)) == 1:
            return False
        for i in range(9, 11):
            soma = sum(int(cpf[j]) * (i + 1 - j) for j in range(i))
            digito = (soma * 10 % 11) % 10
            if digito != int(cpf[i]):
                return False
        return True

    def __str__(self):
        v = self.valor
        return f"{v[:3]}.{v[3:6]}.{v[6:9]}-{v[9:]}"


@dataclass(frozen=True)
class CNPJ:
    valor: str

    def __post_init__(self):
        limpo = re.sub(r"\D", "", self.valor)
        if not self._valido(limpo):
            raise ValueError(f"CNPJ inválido: {self.valor}")
        object.__setattr__(self, "valor", limpo)

    def _valido(self, cnpj: str) -> bool:
        if len(cnpj) != 14 or len(set(cnpj)) == 1:
            return False
        pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        for pesos in (pesos1, pesos2):
            soma = sum(int(cnpj[i]) * pesos[i] for i in range(len(pesos)))
            resto = soma % 11
            digito = 0 if resto < 2 else 11 - resto
            if digito != int(cnpj[len(pesos)]):
                return False
        return True


@dataclass(frozen=True)
class Placa:
    valor: str

    def __post_init__(self):
        formatado = self.valor.upper().strip()
        if not REGEX_PLACA.match(formatado):
            raise ValueError(f"Placa inválida: {self.valor}")
        object.__setattr__(self, "valor", formatado)
