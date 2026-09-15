# ADR-007: Autorização por Principal
## Decisão Permanente
Permissões e roles (CLIENTE, MECANICO, ADMIN) geridas em uma class `Principal` unificada na requisição da API via injecao de dependência `Depends(get_token_provider)`.
