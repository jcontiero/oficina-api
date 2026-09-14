# Requisitos do Negócio - Fase 1 (MVP)

## Desafio
Uma oficina mecânica de médio porte, especializada em manutenção de veículos, tem enfrentado desafios para expandir seus serviços com qualidade e eficiência. Atualmente, o processo é feito de forma desorganizada, gerando:
- Erros na priorização dos atendimentos;
- Falhas no controle de peças e insumos;
- Dificuldade em acompanhar o status dos serviços;
- Perda de histórico de clientes e veículos;
- Ineficiência no fluxo de orçamentos e autorizações.

Diante disso, a oficina decidiu investir em um Sistema Integrado de Atendimento e Execução de Serviços, que permitirá aos clientes acompanhar em tempo real o andamento do serviço, autorizar reparos adicionais via aplicativo e garantir uma gestão interna eficiente e segura.

## Proposta
Desenvolver a primeira versão (MVP) do back-end do sistema da oficina, com foco em gestão de ordens de serviço, clientes e peças, aplicando Domain Driven Design (DDD) e garantindo boas práticas de Qualidade de Software e Segurança.

## Funcionalidades obrigatórias
### Fluxos principais
**Criação da Ordem de Serviço (OS):**
- Identificação do cliente por CPF/CNPJ;
- Cadastro de veículo (placa, marca, modelo, ano);
- Inclusão dos serviços solicitados (exemplo: troca de óleo, alinhamento);
- Possibilidade de incluir peças e insumos necessários;
- Orçamento gerado automaticamente com base nos serviços e peças;
- Envio do orçamento ao cliente para aprovação.

**Acompanhamento da OS:**
- Status da OS: Recebida, Em diagnóstico, Aguardando aprovação, Em execução, Finalizada, Entregue.
- Alteração automática dos status conforme ações no sistema;
- Permitir consulta por parte do cliente via API para acompanhar o progresso.

### Gestão administrativa:
- CRUD de clientes;
- CRUD de veículos;
- CRUD de serviços;
- CRUD de peças e insumos, com controle de estoque;
- Listagem e detalhamento de ordens de serviço;
- Monitoramento do tempo médio de execução dos serviços.

### Segurança e qualidade:
- Implementação de autenticação JWT para APIs administrativas;
- Validação dos dados sensíveis (CPF/CNPJ, placa de veículo);
- Testes unitários e de integração para os principais fluxos.

## Requisitos técnicos
- Back-end monolítico (Monolito em camadas).
- APIs RESTful documentadas via Swagger ou similar.
- Dockerfile para build da aplicação e docker-compose.yml para orquestrar.
- Testes automatizados com cobertura mínima de 80% nos domínios críticos.
