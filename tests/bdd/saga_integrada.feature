# language: pt
Funcionalidade: Orquestração distribuída de Ordem de Serviço via Saga, Outbox/Inbox e Pub/Sub

  Cenário: Fluxo feliz completo pelas três APIs, emuladores e provedor de pagamento fake
    Dado que a stack integrada com os três serviços, PostgreSQL, Firestore Emulator e Pub/Sub Emulator está saudável
    Quando executo o fluxo E2E completo de abertura até entrega com pagamento aprovado
    Então a Saga conclui em CONCLUIDA, a OS atinge ENTREGUE e o estoque reservado permanece debitado

  Cenário: Compensação completa após recusa de pagamento e retomada do orquestrador após reinício
    Dado que a stack integrada com os três serviços, PostgreSQL, Firestore Emulator e Pub/Sub Emulator está saudável
    Quando o worker do orquestrador reinicia em etapa pendente e o pagamento é recusado após reserva de peças
    Então a Saga retoma pelo estado persistido, exige a barreira de cancelamento, restaura o estoque e conclui em COMPENSADA
