# ADR-006: JWT RS256 com KMS e JWKS
## Decisão Permanente
O JWT emitido possui assinatura assimétrica RS256. A chave privada é mantida no GCP KMS ou secret, e a publica exposta pelo endpoint `.well-known/jwks.json`.
