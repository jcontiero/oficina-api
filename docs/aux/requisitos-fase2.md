# Requisitos do Negócio - Fase 2 (Escalabilidade e Infraestrutura)

## O problema
Após a implantação do sistema inicial (Fase 1), a oficina mecânica conquistou maior eficiência no atendimento. Porém, com o aumento da demanda, surgiu a necessidade de evoluir a aplicação para:
- Reduzir riscos operacionais por meio de infraestrutura escalável;
- Automatizar o provisionamento e o deploy do ambiente;
- Melhorar a qualidade e a organização do código;
- Preparar a aplicação para suportar grandes volumes de ordens de serviço em horários de pico.

## Objetivo
Evoluir a aplicação desenvolvida na Fase 1 para garantir qualidade, resiliência e escalabilidade, incorporando práticas modernas de infraestrutura e automação.

## Requisitos obrigatórios

### Evolução da aplicação
- Refatorar o código da fase 1 aplicando Clean Code e Clean Architecture ou Arquitetura Hexagonal.
- Testes automatizados (unitários e/ou integração) para cobrir os fluxos críticos.
- Alterar/criar as seguintes APIs:
  - **Abertura de Ordem de Serviço (OS)**: receber os dados do cliente, veículo, serviços e peças, retornando a identificação única da OS.
  - **Consulta de status da OS**: informar a situação atual (Recebida, Diagnóstico, Aguardando Aprovação, Execução, Finalizada, Entregue).
  - **Aprovação de orçamento**: endpoint para receber notificações externas de aprovação ou recusa do orçamento do cliente.
  - **Listagem de ordens de serviço**: Ordenação por status (Em Execução > Aguardando Aprovação > Diagnóstico > Recebida) e Mais antigas primeiro. Excluir da listagem as OS finalizadas e entregues.
  - **Atualização de status da OS** via alguma ferramenta como e-mail.

### Infraestrutura
- **Conteinerização**: Garantir a aplicação containerizada via Docker (Dockerfile e docker-compose).
- **Orquestração com Kubernetes (K8s)**: Criar manifestos YAML (Deployments, Services, ConfigMaps, Secrets, Horizontal Pod Autoscaler - HPA).
- **Infraestrutura como Código (IaC)**: Scripts em Terraform para provisionamento do cluster Kubernetes e Banco de Dados.
- **CI/CD**: Pipeline (GitHub Actions, GitLab CI, etc.) executando testes, build Docker, deploy Kubernetes e deploy banco de dados.
