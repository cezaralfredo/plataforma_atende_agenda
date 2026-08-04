# Arquitetura — Plataforma Agenda Beleza + Hermes Agent + Asaas

## Stack Tecnológico

| Componente | Tecnologia |
|---|---|
| Backend | Python + FastAPI + Uvicorn |
| ORM | SQLAlchemy + Alembic |
| Banco | PostgreSQL |
| Agente IA | Hermes Agent (Nous Research) |
| LLM | Nous Hermes (via Together AI / Fireworks / Nous Portal) |
| Pagamentos | Asaas (PIX, boleto, cartão) |
| Canal | WhatsApp (gateway nativo do Hermes) |
| Integração IA-Plataforma | MCP (Model Context Protocol) |

---

## Arquitetura Geral

```
                    ┌──────────────────────────────────────────────┐
                    │          HERMES AGENT (Nous Research)         │
                    │                                               │
                    │  ┌──────────────────┐  ┌──────────────────┐  │
                    │  │ Gateway WhatsApp  │  │ Cron Scheduler    │ │
                    │  │ (conversa c/     │  │ (tarefas         │  │
                    │  │  clientes)       │  │  automáticas)    │  │
                    │  └──────────────────┘  └──────────────────┘  │
                    │                                               │
                    │  ┌──────────────────────────────────────┐    │
                    │  │         KANBAN MULTI-AGENT            │    │
                    │  │  ┌──────────┐ ┌──────────┐          │    │
                    │  │  │ Orques-  │ │ Agendador│          │    │
                    │  │  │ trador   │ └──────────┘          │    │
                    │  │  └──────────┘                       │    │
                    │  │  ┌──────────┐ ┌──────────┐          │    │
                    │  │  │ Finan-   │ │ Notifi-  │          │    │
                    │  │  │ ceiro    │ │ cador    │          │    │
                    │  │  └──────────┘ └──────────┘          │    │
                    │  └──────────────────────────────────────┘    │
                    │                                               │
                    │  ┌──────────────────────────────────────┐    │
                    │  │  MCP Client                          │────┼────┐
                    │  └──────────────────────────────────────┘    │    │
                    └──────────────────────────────────────────────┘    │
                                                                       │
┌──────────────────────────────────────────────────────────────────┐   │
│              SERVIDOR MCP / API (FastAPI)                         ◄───┘
│                                                                   │
│  ┌──────────────────────┐  ┌────────────────────────────────┐   │
│  │  MCP Tools Layer      │  │  Webhook Receiver              │   │
│  │                       │  │  (/webhooks/asaas)             │   │
│  │  - listar_servicos    │  └────────────┬───────────────────┘   │
│  │  - verificar_horario  │               │                       │
│  │  - criar_reserva      │      ┌────────▼────────┐             │
│  │  - criar_cobranca     │      │  Asaas API       │             │
│  │  - verificar_pgto     │      │  (REST + WH)     │             │
│  │  - confirmar_pgto     │      └─────────────────┘             │
│  │  - cancelar_reserva   │                                       │
│  └──────────────────────┘                                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Core Services                                            │  │
│  │  (Profissionais, Serviços, Agenda, Pagamentos)            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  PostgreSQL                                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Agentes (Hermes Profiles)

Cada agente é um perfil Hermes com toolsets específicos. Trabalham via Kanban.

| Agente | Perfil | Função | Toolsets |
|---|---|---|---|
| **Orquestrador** | `orquestrador` | Recebe WhatsApp, coordena fluxo, delega tarefas | `kanban`, `gateway`, `memory` |
| **Agendador** | `agendador` | Verifica disponibilidade, cria reservas | `kanban`, MCP scheduling |
| **Financeiro** | `financeiro` | Cria cobranças Asaas, monitora pagamentos | `kanban`, MCP payments, `cron` |
| **Notificador** | `notificador` | Envia confirmações, lembretes, avisos | `kanban`, `gateway` (send) |

---

## Fluxo Kanban Multi-Agent

```
CLIENTE WHATSAPP: "Quero cortar cabelo com Maria amanhã 15h"

ORQUESTRADOR (sessão WhatsApp ativa)
  1. MCP: verificar_disponibilidade("Maria", "amanhã 15h")
  2. MCP: criar_reserva(cliente, Maria, corte, 15h)
  3. kanban_create(title="Criar cobrança R$50", assignee="financeiro",
                    body="Reserva t_a1b2. Gerar link Asaas.")
  4. kanban_complete()

FINANCEIRO (worker isolado)
  1. kanban_show() → lê body
  2. MCP: criar_cobranca_asaas(João, 5000, "Corte Maria 15h")
       → Asaas API: POST /payments → {invoiceUrl, id}
  3. kanban_create(title="Notificar João link pagamento",
                   assignee="notificador",
                   body="Link: https://asaas.com/pay/xyz")
  4. kanban_complete()

NOTIFICADOR (worker isolado)
  1. WhatsApp: "💳 Pagamento: [link]"
  2. kanban_complete()

(pagamento acontece)
Asaas → Webhook → FastAPI: PAYMENT_RECEIVED
  → Atualiza payment.status = "received"

(cron: a cada 3min)
FINANCEIRO (cron job c/ wakeAgent gate)
  1. MCP: verificar_pagamentos_recentes()
  2. Se encontrou → kanban_create(assignee="notificador",
                    body="Pagamento R$50 confirmado! Reserva t_a1b2. Maria amanhã 15h.")
  3. kanban_complete()

NOTIFICADOR (worker isolado)
  1. WhatsApp: "✅ Pagamento confirmado! Corte com Maria amanhã 15h garantido! 🎉"
  2. kanban_complete()
```

---

## Modelo de Dados (PostgreSQL)

```sql
-- Clientes
users: id, name, phone, email, asaas_customer_id, created_at

-- Profissionais
professionals: id, name, phone, email, bio, photo_url, active

-- Serviços
services: id, professional_id, name, description,
          duration_minutes, price_cents, category

-- Disponibilidade
availability: id, professional_id, day_of_week (0-6),
              start_time, end_time, specific_date

-- Agendamentos
appointments: id, user_id, professional_id, service_id,
              start_time, end_time,
              status (pending|awaiting_payment|confirmed|cancelled|completed),
              expires_at, notified_at, notes, created_at

-- Pagamentos (Asaas)
payments: id, appointment_id, asaas_payment_id, amount_cents,
          billing_type (pix|boleto|credit_card),
          status (pending|confirmed|received|overdue|refunded|cancelled),
          invoice_url, received_at, created_at, updated_at

-- Log de notificações
notification_log: id, appointment_id, type (confirmation|reminder|expiration),
                  sent_at
```

---

## MCP Tools

| Tool | Domínio | Chamada por | Descrição |
|---|---|---|---|
| `listar_servicos` | Agenda | Orquestrador, Agendador | Lista serviços por profissional/categoria |
| `verificar_disponibilidade` | Agenda | Orquestrador, Agendador | Horários livres em data específica |
| `criar_reserva` | Agenda | Agendador | Cria appointment (awaiting_payment) com expiração |
| `cancelar_reserva` | Agenda | Agendador | Cancela reserva |
| `criar_cobranca_asaas` | Financeiro | Financeiro | Cria cobrança no Asaas, retorna link |
| `verificar_pagamentos_recentes` | Financeiro | Financeiro (cron) | Lista pagamentos received não notificados |
| `marcar_notificado` | Financeiro | Notificador | Marca notified_at no appointment |
| `meus_agendamentos` | Agenda | Orquestrador | Lista agendamentos do cliente |

---

## Integração Asaas

### Criação de Cobrança
```
POST /v3/payments
{
  "customer": "cus_0001",
  "billingType": "UNDEFINED",
  "value": 50.00,
  "dueDate": "2026-07-29",
  "description": "Corte de cabelo - Maria - 15h"
}
```
→ Retorna: `{ "id": "pay_123", "invoiceUrl": "https://..." }`

### Webhooks Recebidos
| Evento | Ação |
|---|---|
| `PAYMENT_RECEIVED` | Libera agendamento |
| `PAYMENT_CONFIRMED` | Atualiza status (cartão) |
| `PAYMENT_OVERDUE` | Notifica cliente |
| `PAYMENT_REFUNDED` | Cancela agendamento |

### Segurança
- Valida header `asaas-access-token`
- Idempotência via `event` + `payment.id`
- Response HTTP 200 imediato

---

## Configuração Hermes

```yaml
# ~/.hermes/config.yaml

mcp_servers:
  agenda_atende:
    url: "http://localhost:8000/mcp"
    headers:
      Authorization: "Bearer ${AGENDA_API_KEY}"

kanban:
  dispatch_in_gateway: true
  dispatch_interval_seconds: 30
  auto_decompose: false
  orchestrator_profile: "orquestrador"
  failure_limit: 2

gateway:
  platforms:
    whatsapp:
      enabled: true
```

## Perfis

```bash
hermes profile create orquestrador \
  --description "Coordenador central. Recebe msgs do cliente via WhatsApp, \
                 delega tarefas para especialistas via Kanban, \
                 sintetiza resultados e responde ao cliente."

hermes profile create agendador \
  --description "Especialista em agenda. Consulta disponibilidade \
                 no MCP, cria reservas, valida horários."

hermes profile create financeiro \
  --description "Especialista em pagamentos. Cria cobranças no Asaas, \
                 monitora confirmações, gerencia estornos."

hermes profile create notificador \
  --description "Envia mensagens aos clientes via WhatsApp: \
                 confirmações, lembretes, avisos de cancelamento."
```

---

## Fases de Implementação

| Fase | Duração | Entregas |
|---|---|---|
| 1. Fundação | 1 semana | FastAPI + SQLAlchemy + PostgreSQL + Models + Migrations |
| 2. Core | 1 semana | CRUDs Profissionais/Serviços + Lógica de disponibilidade + CRUD Appointment |
| 3. Asaas | 1 semana | Integração API Asaas (criar cliente, criar cobrança) + Webhook receiver |
| 4. MCP Server | 1 semana | Servidor MCP em Python com todas as tools |
| 5. Hermes Setup | 3 dias | Instalação + Perfis + Config WhatsApp + Config MCP + Kanban init |
| 6. Fluxo Completo | 3 dias | Teste E2E: WhatsApp → reserva → pagamento → confirmação |

---

## Decisões Pendentes

1. **Dependência entre tarefas**: Financeiro roda em paralelo ao Agendador ou apenas após reserva confirmada?
2. **Confirmação de pagamento**: Cron puro (polling a cada 3min) ou Event Hook via webhook no Hermes?
3. **Notificador**: Separado (worker próprio) ou embutido no Orquestrador?
4. **Provedor LLM**: Together AI, Fireworks AI, ou Nous Portal (com Tool Gateway)?
5. **Expiração da reserva**: 30min é o ideal? Cliente pode solicitar mais tempo?
