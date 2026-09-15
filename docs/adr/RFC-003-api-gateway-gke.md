# RFC-003: API Gateway GKE
## Contexto
Proteção das origens e centralização das rotas.
## Decisão
O API Gateway do GCP roteará o prefixo `/auth` para a Cloud Function e o restante como backend service via Network Endpoint Group (NEG) apontado para o GKE (oficina-api). 
