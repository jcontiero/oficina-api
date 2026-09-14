# Relatório — Etapa 7: Documentação e Vídeo

**Projeto:** Oficina Mecânica API — Fase 2  
**Data:** 08/07/2026  
**Responsável:** Jonas Vasconcelos

---

## 1. Objetivo

Atualizar a documentação do projeto para refletir o estado final da Fase 2, criar uma collection de APIs e preparar as orientações para o vídeo demonstrativo.

---

## 2. Entregáveis

### 2.1 `README.md` atualizado

O README foi reescrito para cobrir:

- **Objetivos da Fase 2:** Clean Architecture, APIs de OS, Docker, Kubernetes, Terraform e CI/CD.
- **Arquitetura:** visão geral do fluxo (GitHub Actions → Docker → Terraform → Kubernetes), estrutura do código e camadas Clean Architecture.
- **Stack tecnológica:** atualizada com Terraform, Kubernetes, Helm e GitHub Actions.
- **Instruções de execução:**
  - Docker Compose local.
  - Provisionamento Terraform (cluster kind).
  - Deploy no Kubernetes.
- **APIs obrigatórias da Fase 2:** tabela com os 6 endpoints principais.
- **CI/CD:** descrição dos 8 jobs da pipeline e secrets esperados.
- **Checklist da Fase 2** e link para vídeo demonstrativo.

### 2.2 Collection de APIs

Criado o arquivo `docs/collection-postman.json` no formato Postman v2.1, contendo:

- **Autenticação:** login admin.
- **Catálogo:** criar serviço.
- **Estoque:** criar peça.
- **Atendimento:** criar cliente e veículo.
- **Ordens de Serviço (Fase 2):**
  - Abertura unificada.
  - Consultar status.
  - Listagem ordenada.
  - Aprovar orçamento.
  - Recusar orçamento.
- **Webhook:** atualizar status via token.
- **Health:** health check.

Variáveis de collection:

| Variável | Descrição |
|---|---|
| `base_url` | URL base da API (`http://localhost:8000`) |
| `token` | Token JWT retornado no login |
| `cliente_id` | ID do cliente criado |
| `servico_id` | ID do serviço criado |
| `peca_id` | ID da peça criada |
| `os_id` | ID da ordem de serviço |
| `webhook_token` | Token do link de e-mail |

### 2.3 Guia para o vídeo demonstrativo

O README inclui uma seção indicando que o vídeo deve demonstrar:

1. Execução local com Docker Compose.
2. Provisionamento do cluster com Terraform.
3. Deploy da aplicação no Kubernetes.
4. Consumo das APIs obrigatórias da Fase 2.
5. Pipeline CI/CD em execução.
6. Escalonamento automático (HPA).

> O link do vídeo deve ser adicionado manualmente no README após a gravação.

---

## 3. Validação

### 3.1 README

- Estrutura revisada e alinhada aos requisitos da Fase 2.
- Instruções de execução local, Terraform e Kubernetes incluídas.
- Link para collection e placeholder para vídeo adicionados.

### 3.2 Collection Postman

```bash
python3 -c "import json; json.load(open('docs/collection-postman.json')); print('Collection JSON válido')"
```

Resultado: `Collection JSON válido`.

---

## 4. Próximos passos

- Gravar o vídeo demonstrativo de até 15 minutos.
- Substituir o placeholder no README pelo link real do vídeo.
- Realizar uma validação end-to-end completa antes da entrega final.
