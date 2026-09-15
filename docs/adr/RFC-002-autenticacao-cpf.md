# RFC-002: Autenticacao por CPF
## Contexto
Necessidade do Tech Challenge de autenticar o usuário provendo o CPF.
## Decisão
A function "oficina-auth-function" será a encarregada de verificar o CPF via regex/algoritmo e validar na tabela de clientes. Caso seja válido, emite-se um token JWT. O risco do CPF como dado sensível é mitigado não o expondo desnecessariamente nas claims e isolando a autenticacao via API Gateway.
