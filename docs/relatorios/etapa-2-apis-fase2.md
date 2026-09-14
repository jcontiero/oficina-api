# Relatório — Etapa 2: APIs de Ordem de Serviço (Fase 2)

**Data:** 07/07/2026  
**Status:** Concluído

## Objetivo

Implementar as cinco APIs obrigatórias da Fase 2 para ordens de serviço, mantendo a arquitetura Clean/Hexagonal estabelecida na Etapa 1.

## APIs implementadas

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/ordens-de-servico` | Abertura unificada (cliente, veículo, serviços e peças) |
| `GET` | `/ordens-de-servico/{id}/status` | Consulta de status no formato da Fase 2 |
| `POST` | `/ordens-de-servico/{id}/aprovacao` | Aprovação ou recusa do orçamento |
| `GET` | `/ordens-de-servico` | Listagem ordenada e filtrada |
| `POST` | `/webhooks/os/{id}/atualizar-status` | Atualização de status via token seguro |

## Mudanças realizadas

### 1. Status da Fase 2

- Criado enum `StatusOSFase2` em `src/atendimento/dominio/value_objects.py` com os 6 status exigidos: Recebida, Diagnóstico, Aguardando Aprovação, Execução, Finalizada, Entregue.
- Criadas funções de mapeamento `para_status_fase2` e `para_status_interno`.
- Ajustadas transições válidas: recusa volta para `Diagnóstico`; abertura unificada percorre Recebida → Diagnóstico → Aguardando Aprovação.

### 2. Exceções de domínio

- Criadas `TransicaoDeStatusInvalidaError`, `TokenDeAprovacaoInvalidoError`, `TokenDeAprovacaoExpiradoError`.
- `TransicaoInvalidaError` mantida como compatibilidade herdando de `TransicaoDeStatusInvalidaError`.

### 3. Casos de uso novos

- `AbrirOrdemDeServicoUnificada`: cria ou reutiliza cliente e veículo, adiciona serviços/peças e gera orçamento.
- `ConsultarStatusOrdemDeServico`: retorna o status no formato da Fase 2.
- `ProcessarAprovacaoOrcamento`: aprova (vai para Execução) ou recusa (volta para Diagnóstico).
- `ListarOrdensDeServicoAtivas`: ordena por prioridade e oculta Finalizadas/Entregues/Canceladas.
- `AtualizarStatusViaWebhook`: valida token JWT e atualiza status respeitando transições.

### 4. Token de aprovação/webhook

- `ProvedorToken.criar` aceita `expiracao_horas` opcional.
- Tokens JWT são usados para validar o webhook de atualização de status.

### 5. Rotas e schemas

- `POST /ordens-de-servico` substituído pelo contrato unificado.
- `GET /ordens-de-servico` retorna listagem ordenada da Fase 2.
- Adicionadas rotas de status, aprovação e webhook.
- Mantidas rotas auxiliares antigas (`/iniciar-diagnostico`, `/aprovar-orcamento`, etc.) para compatibilidade interna.

### 6. Testes

- Atualizados testes de integração de OS para o novo contrato de abertura.
- Criados testes de integração para as 5 novas APIs.
- Criados testes unitários para os novos casos de uso (`tests/unit/atendimento/test_casos_de_uso_fase2.py`).
- Criados testes unitários para casos de uso existentes de atendimento (`tests/unit/atendimento/test_casos_de_uso.py`), elevando a cobertura de `atendimento/aplicacao`.

## Validação

| Verificação | Comando | Resultado |
|---|---|---|
| Lint | `ruff check src tests scripts` | ✅ passou |
| Testes | `pytest tests/` | ✅ **186 passaram** |
| Cobertura total | `pytest --cov=src` | ✅ **87.37%** |
| Cobertura `dominio/` | — | ✅ > 95% |
| Cobertura `aplicacao/` | — | ✅ > 80% em todos os módulos |

## Arquivos principais criados

- `tests/unit/atendimento/test_casos_de_uso_fase2.py`
- `tests/unit/atendimento/test_casos_de_uso.py`

## Arquivos principais alterados

- `src/atendimento/dominio/value_objects.py`
- `src/atendimento/dominio/excecoes.py`
- `src/atendimento/dominio/entidades.py`
- `src/atendimento/aplicacao/casos_de_uso.py`
- `src/atendimento/apresentacao/rotas.py`
- `src/atendimento/apresentacao/schemas.py`
- `src/identidade/aplicacao/ports.py`
- `src/identidade/infraestrutura/jwt_provider.py`
- `src/container.py`
- `tests/integration/test_ordens_de_servico.py`
- `tests/unit/atendimento/test_ordem_de_servico.py`

## Próxima etapa

Etapa 3: Docker (reescrever Dockerfile multi-stage, docker-compose revisado, health check e separação de migrations/seeds).
