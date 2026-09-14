# Relatório — Etapa 1: Refatoração Arquitetural (Clean Architecture/Hexagonal)

**Data:** 07/07/2026  
**Status:** Concluído

## Objetivo

Evoluir a arquitetura do MVP da Fase 1 para Clean Architecture/Hexagonal, conforme planejado na Fase 2, estabelecendo a base sólida para as novas APIs e infraestrutura.

## Mudanças realizadas

### 1. Inversão de dependências — Ports e Adapters

| Porta | Localização | Implementação |
|---|---|---|
| `ProvedorToken` | `src/identidade/aplicacao/ports.py` | `JwtTokenProvider` |
| `ProvedorHashSenha` | `src/identidade/aplicacao/ports.py` | `BcryptHashProvider` |
| `Notificador` | `src/atendimento/aplicacao/ports.py` | `SmtpNotificador` |
| `NotificadorEstoque` | `src/estoque/aplicacao/ports.py` | `SmtpNotificador` |
| `ConsultaRelatorios` | `src/relatorios/aplicacao/ports.py` | `RelatorioConsultaImpl` |

### 2. Container de injeção de dependências

Criado `src/container.py`, ponto único de composição da aplicação. Todas as rotas passaram a receber casos de uso via `Depends`, eliminando a instanciação direta de repositórios concretos.

### 3. Remoção de singletons globais

- `src/config.py`: removida a instância global `configuracoes = Configuracoes()`.
- `src/shared/banco.py`: removidos `engine` e `SessionLocal` globais; mantido apenas `Base`.
- Configuração e engine agora são criados no `Container` e injetados.

### 4. Movimentação de serviços concretos

- `src/shared/seguranca.py` → removido; lógica migrada para `JwtTokenProvider` e `BcryptHashProvider`.
- `src/shared/notificacoes.py` → removido; lógica migrada para `SmtpNotificador`.

### 5. Refatoração de casos de uso

- `identidade/aplicacao/casos_de_uso.py`: `AutenticarUsuario` e `CriarUsuario` recebem ports.
- `atendimento/aplicacao/casos_de_uso.py`: casos de uso que notificam recebem `Notificador`; `OrdemDeServicoNaoEncontradaError` substitui `ValueError`.
- `estoque/aplicacao/casos_de_uso.py`: `ReporEstoque` recebe `NotificadorEstoque`.
- `relatorios/aplicacao/casos_de_uso.py`: criado `GerarRelatorioTempoMedioDeServicos`; query SQLAlchemy removida da rota.

### 6. Remoção de `setattr` dinâmico

`AtualizarCliente`, `AtualizarVeiculo` e `AtualizarPeca` passaram a receber parâmetros tipados explicitamente.

### 7. Ajustes em rotas e autenticação

- Rotas de todos os módulos atualizadas para `Depends` do container.
- `src/shared/dependencias.py` atualizado para receber `ProvedorToken` via injeção.
- `src/main.py` refatorado para expor `criar_app()` e registrar o container.

### 8. Testes

- Ajustados testes de integração (`conftest.py`, `test_auth.py`).
- Atualizados testes unitários de autenticação e notificações.
- Criados testes unitários para casos de uso de estoque (`tests/unit/estoque/test_casos_de_uso.py`).
- Criados testes unitários para caso de uso de relatórios (`tests/unit/relatorios/test_casos_de_uso.py`).

### 9. Dependências de desenvolvimento

Adicionados `ruff` e `black` ao `pyproject.toml`.

## Validação

| Verificação | Comando | Resultado |
|---|---|---|
| Lint | `ruff check src tests scripts` | ✅ passou |
| Testes | `pytest tests/` | ✅ **140 passaram** |
| Cobertura total | `pytest --cov=src` | ✅ **88%** |
| Cobertura `dominio/` | — | ✅ > 95% |
| Cobertura `aplicacao/` | — | ✅ > 80% em todos os módulos |

## Arquivos principais criados

- `src/container.py`
- `src/identidade/aplicacao/ports.py`
- `src/identidade/infraestrutura/jwt_provider.py`
- `src/identidade/infraestrutura/bcrypt_provider.py`
- `src/atendimento/aplicacao/ports.py`
- `src/estoque/aplicacao/ports.py`
- `src/relatorios/aplicacao/ports.py`
- `src/relatorios/aplicacao/dto.py`
- `src/relatorios/aplicacao/casos_de_uso.py`
- `src/relatorios/infraestrutura/consulta_relatorios.py`
- `src/shared/infraestrutura/notificador_smtp.py`
- `tests/unit/estoque/test_casos_de_uso.py`
- `tests/unit/relatorios/test_casos_de_uso.py`

## Arquivos principais alterados

- `src/config.py`
- `src/shared/banco.py`
- `src/shared/dependencias.py`
- `src/main.py`
- `src/identidade/aplicacao/casos_de_uso.py`
- `src/identidade/apresentacao/rotas.py`
- `src/atendimento/aplicacao/casos_de_uso.py`
- `src/atendimento/apresentacao/rotas.py`
- `src/atendimento/dominio/excecoes.py`
- `src/estoque/aplicacao/casos_de_uso.py`
- `src/estoque/apresentacao/rotas.py`
- `src/relatorios/apresentacao/rotas.py`
- `scripts/seed_mock.py`
- `tests/integration/conftest.py`
- `tests/integration/test_auth.py`
- `tests/unit/identidade/test_autenticacao.py`
- `tests/unit/shared/test_notificacoes.py`
- `pyproject.toml`

## Próxima etapa

Etapa 2: implementação das APIs obrigatórias da Fase 2.
