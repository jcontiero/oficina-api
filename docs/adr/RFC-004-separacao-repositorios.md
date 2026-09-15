# RFC-004: Separação de Repositórios
## Contexto
O monolito estava dificultando o release e ownership.
## Decisão
O monolito foi fragmentado em 4 repos: api, k8s-infra, database-infra e serverless. Cada repo com seu fluxo CI independente no Github Actions.
