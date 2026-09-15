# RFC-005: Notificacoes Serverless
## Contexto
O envio de e-mail pode falhar e travar o processamento da API de Ordens de Servico.
## Decisão
Utilizaremos Google Cloud Pub/Sub e Eventarc ligados a uma Cloud Function isolada para notificação assincrona.
