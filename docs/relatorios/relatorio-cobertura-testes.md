# Cobertura de testes da Fase 4

O requisito é cobertura mínima de 80% por microsserviço. O CI aplica o limite com pytest-cov e executa análise de qualidade no SonarCloud. A aprovação de um serviço não substitui a dos demais.

## Evidências registradas

A validação local de fechamento em 17/11/2026 registrou:

| Serviço | Testes aprovados | Cobertura |
| --- | ---: | ---: |
| oficina-api | 222 | 88,73% |
| oficina-billing | 30 | 87,91% |
| oficina-execucao | 70 | 87,33% |

Resultados registrados na execução de fechamento de 17/11/2026. São uma fotografia histórica; confira os workflows abaixo para o commit atual.

Na correção posterior da integração externa Mercado Pago, Billing registrou 33 testes aprovados e 87,63% de cobertura local. O [PR Billing 19](https://github.com/jcontiero/oficina-billing/pull/19) passou em CI e Sonar; o [deploy de homologação](https://github.com/jcontiero/oficina-billing/actions/runs/44223204355) implantou o commit `c5208089e95a8fddfb4aca41152d690a0bbf4e77`. Resultados de suítes e commits distintos não devem ser somados.

## Conferir o commit atual

- [CI da API](https://github.com/jcontiero/oficina-api/actions).
- [CI do Billing](https://github.com/jcontiero/oficina-billing/actions).
- [CI de Execução](https://github.com/jcontiero/oficina-execucao/actions).

Confira o SHA analisado, a saída de pytest e o Quality Gate do SonarCloud. Uma porcentagem histórica não comprova a cobertura de alterações posteriores.

## Reproduzir a suíte da API

Na raiz de oficina-api, instale as dependências com `uv sync --all-extras` e execute o comando de cobertura usado no job validate:

```bash
DD_TRACE_ENABLED=false \
TEST_DATABASE_URL=sqlite:////tmp/oficina_ci_test.db \
SECRET_KEY=ci-secret-key-para-testes-32-chars-ok \
uv run pytest tests/unit tests/integration --cov=src --cov-fail-under=80 -q
```

Use um banco descartável de testes. Para Billing e Execução, siga os workflows dos respectivos repositórios, com suas dependências e configurações próprias.

## BDD integrado

O job bdd-integrado da API sobe três APIs, três workers, PostgreSQL e emuladores Firestore/PubSub. Executa os cenários de fluxo feliz e compensação/reinício em duas rodadas sobre a mesma stack, registra os SHAs e publica JUnit e logs no artefato bdd-integrado-relatorios.

Os cenários estão em `tests/bdd/saga_integrada.feature`, com steps em `tests/bdd/test_p6_bdd_integrado.py`. O provedor financeiro desses testes é fake. O aceite externo Mercado Pago em homologação é uma execução separada e não entra nessa medição de cobertura.
