# Plataforma Atende Agenda

API REST completa para gestão de agendamentos, profissionais, serviços e pagamentos — construída com **FastAPI**, **SQLAlchemy** e **PostgreSQL**. Inclui integração com **Asaas** para pagamentos e suporte a **MCP (Model Context Protocol)** para agentes de IA.

---

## Funcionalidades Principais

### Gestão de Usuários
- CRUD completo de usuários (clientes)
- Busca por telefone com validação de duplicidade
- Vinculação de número WhatsApp

### Gestão de Profissionais
- CRUD de profissionais (prestadores de serviço)
- Filtro por profissionais ativos/inativos

### Gestão de Serviços
- Catálogo único de serviços, com nome, descrição e categoria
- Oferta por profissional com preço, duração e comissão configuráveis
- Listagens comerciais retornam somente ofertas ativas

### Disponibilidade e Agenda
- Definição de horários de trabalho por profissional (dias da semana, intervalos)
- Consulta de slots disponíveis para data específica
- Verificação de conflitos de horário
- Geração automática de *time slots* baseada na duração do serviço

### Agendamentos (Appointments)
- Criação de reservas com validação de disponibilidade
- Estados: `pending` → `confirmed` → `completed` / `cancelled`
- Expiração automática de reservas pendentes (30 min)
- Confirmação e cancelamento via API
- Filtros por usuário, profissional e status

### Pagamentos (Integração Asaas)
- Criação de cobranças (PIX, Boleto, Cartão)
- Webhook para atualização automática de status
- Consulta e atualização manual de status de pagamento
- Sincronização: pagamento confirmado → agendamento confirmado

### Webhooks
- Endpoint `/webhooks/asaas` para receber notificações do Asaas
- Validação de assinatura HMAC
- Prevenção de processamento duplicado

### MCP (Model Context Protocol)
- Endpoint `/mcp` para integração com agentes de IA
- Ferramentas disponíveis:
  - `buscar_cliente_por_telefone` — busca cliente por telefone/WhatsApp
  - `cadastrar_cliente` — cadastra novo cliente
  - `atualizar_cliente` — atualiza dados do cliente
  - `vincular_whatsapp` — vincula número WhatsApp ao cliente
  - `listar_servicos` — lista serviços com filtros opcionais
  - `verificar_disponibilidade` — verifica horários livres de um profissional em uma data
  - `criar_reserva` — cria agendamento (valida disponibilidade)
  - `cancelar_reserva` — cancela agendamento existente
  - `criar_cobranca_asaas` — cria cobrança no Asaas (PIX, Boleto, Cartão)
  - `verificar_pagamentos_recentes` — verifica pagamentos pendentes no Asaas
  - `marcar_notificado` — marca agendamento como notificado
  - `meus_agendamentos` — lista agendamentos de um cliente
- Autenticação via Bearer Token (`API_KEY`)

### Hermes (Agentes de IA)
- Configuração para orquestração de agentes via **Hermes**
- Perfis pré-definidos:
  - **Agendador** — gestão de reservas
  - **Financeiro** — pagamentos e cobranças
  - **Notificador** — comunicações (WhatsApp, etc.)
  - **Orquestrador** — coordenação geral
- Integração nativa com MCP da API

---

## Tecnologias

| Camada | Tecnologia |
|--------|------------|
| Framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 |
| Banco | PostgreSQL 16 |
| Migrações | Alembic |
| Pagamentos | Asaas API (sandbox/produção) |
| IA/Agentes | MCP (Model Context Protocol) + Hermes |
| Testes | pytest |
| Container | Docker Compose |

---

## Estrutura do Projeto

```
plataforma_atende_agenda/
├── app/
│   ├── api/              # Rotas da API (FastAPI routers)
│   │   ├── appointments.py
│   │   ├── availability.py
│   │   ├── health.py
│   │   ├── payments.py
│   │   ├── professionals.py
│   │   ├── services.py
│   │   ├── users.py
│   │   └── webhooks.py
│   ├── config.py         # Configurações (Pydantic Settings)
│   ├── database.py       # Engine SQLAlchemy + sessão
│   ├── main.py           # App FastAPI + inclusão de routers
│   ├── mcp/              # Model Context Protocol
│   │   ├── router.py     # Endpoint /mcp
│   │   └── tools.py      # Definição das ferramentas MCP
│   ├── models/           # Models SQLAlchemy
│   │   ├── appointment.py
│   │   ├── availability.py
│   │   ├── notification_log.py
│   │   ├── payment.py
│   │   ├── professional.py
│   │   ├── service.py
│   │   ├── user.py
│   │   └── webhook_event.py
│   ├── repositories/     # Camada de acesso a dados
│   │   ├── appointment_repo.py
│   │   ├── availability_repo.py
│   │   ├── base.py
│   │   ├── payment_repo.py
│   │   ├── professional_repo.py
│   │   ├── service_repo.py
│   │   └── user_repo.py
│   ├── schemas/          # Pydantic schemas (request/response)
│   │   ├── appointment.py
│   │   ├── availability.py
│   │   ├── payment.py
│   │   ├── professional.py
│   │   ├── service.py
│   │   └── user.py
│   └── services/         # Lógica de negócio
│       ├── appointment_service.py
│       ├── asaas_client.py
│       ├── availability_service.py
│       ├── payment_service.py
│       ├── payment_state_service.py
│       ├── professional_service.py
│       ├── service_service.py
│       └── user_service.py
├── alembic/              # Migrações de banco
├── hermes/               # Configuração agentes IA
│   ├── config.yaml
│   └── profiles/
├── tests/                # Testes automatizados
├── docker-compose.yml    # PostgreSQL
├── requirements.txt
└── .env                  # Variáveis de ambiente (não versionado)
```

---

## Endpoints da API

### Health
```
GET  /health
```

### Usuários
```
POST   /api/users
GET    /api/users
GET    /api/users/{id}
PUT    /api/users/{id}
DELETE /api/users/{id}
```

### Profissionais
```
POST   /api/professionals
GET    /api/professionals
GET    /api/professionals/{id}
PUT    /api/professionals/{id}
DELETE /api/professionals/{id}
```

### Serviços
```
POST   /api/services
GET    /api/services
GET    /api/services/{id}
PUT    /api/services/{id}
DELETE /api/services/{id}
```

### Disponibilidade
```
POST   /api/availability
GET    /api/availability
GET    /api/availability/{id}
PUT    /api/availability/{id}
DELETE /api/availability/{id}
GET    /api/availability/check/{professional_id}?date=YYYY-MM-DD
GET    /api/availability/slots/{professional_id}/{service_id}?date=YYYY-MM-DD
```

### Agendamentos
```
POST   /api/appointments
GET    /api/appointments
GET    /api/appointments/{id}
PUT    /api/appointments/{id}
POST   /api/appointments/{id}/cancel
POST   /api/appointments/{id}/confirm
DELETE /api/appointments/{id}
```

### Pagamentos
```
POST   /api/payments
GET    /api/payments/{id}
POST   /api/payments/{id}/refresh
POST   /api/payments/verify-recent
```

### Webhooks
```
POST   /webhooks/asaas
```

### MCP
```
POST   /mcp
```

---

## Configuração e Execução

### 1. Variáveis de Ambiente
Crie um arquivo `.env` na raiz:

```env
DATABASE_URL=postgresql+psycopg://agenda_user:agenda_pass@localhost:5432/agenda_atende
API_KEY=sua-chave-secreta-aqui
APP_NAME=Agenda Atende
DEBUG=true

ASAAS_API_KEY=sua-chave-asaas
ASAAS_BASE_URL=https://api-sandbox.asaas.com/v3
ASAAS_WEBHOOK_TOKEN=token-do-webhook-asaas
```

### 2. Subir Banco de Dados (Docker)
```bash
docker-compose up -d
```

### 3. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 4. Executar Migrações
```bash
alembic upgrade head
```

### 5. Iniciar API
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Acesse a documentação interativa: **http://localhost:8000/docs**

---

## Testes

```bash
pytest tests/ -v
```

---

## Integração com Asaas

1. Crie conta no [Asaas](https://www.asaas.com/)
2. Configure `ASAAS_API_KEY` e `ASAAS_WEBHOOK_TOKEN` no `.env`
3. No painel Asaas, configure webhook para: `https://seu-dominio.com/webhooks/asaas`
4. Eventos suportados: `PAYMENT_RECEIVED`, `PAYMENT_CONFIRMED`, `PAYMENT_OVERDUE`, `PAYMENT_REFUNDED`, `PAYMENT_CANCELLED`

---

## MCP + Agentes IA

### Configuração local do Cliente MCP
```json
{
  "mcpServers": {
    "agenda_atende": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer sua-api-key"
      }
    }
  }
}
```

### Ferramentas Disponíveis
| Ferramenta | Descrição |
|------------|-----------|
| `buscar_cliente_por_telefone` | Busca cliente por telefone/WhatsApp |
| `cadastrar_cliente` | Cadastra novo cliente |
| `atualizar_cliente` | Atualiza dados do cliente |
| `vincular_whatsapp` | Vincula número WhatsApp ao cliente |
| `listar_servicos` | Lista serviços com filtros opcionais |
| `verificar_disponibilidade` | Verifica horários livres de um profissional em uma data |
| `criar_reserva` | Cria agendamento (valida disponibilidade) |
| `cancelar_reserva` | Cancela agendamento existente |
| `criar_cobranca_asaas` | Cria cobrança no Asaas (PIX, Boleto, Cartão) |
| `verificar_pagamentos_recentes` | Verifica pagamentos pendentes no Asaas |
| `marcar_notificado` | Marca agendamento como notificado |
| `meus_agendamentos` | Lista agendamentos de um cliente |

### Hermes (Orquestração de Agentes)

**Arquitetura com MCP Gateway (Recomendado para Produção):**

```
Hermes (host/VM) ──► MCP Gateway (Docker) ──► API (Docker)
     │                    │                      │
     │ gateway toolset    │ FastAPI proxy        │ /mcp endpoint
     │                    │ injeta API_KEY       │
     ▼                    ▼                      ▼
  Profis YAML         http://mcp-gateway:8080  PostgreSQL
```

O **MCP Gateway** isola o Hermes do ambiente interno da API:
- Hermes usa apenas o toolset `gateway` (HTTP nativo)
- Gateway injeta `Authorization: Bearer <API_KEY>` automaticamente
- Gateway valida `X-Gateway-Key` para autenticação Hermes→Gateway
- Elimina conflitos de namespace, auth e estado entre Hermes e API

```bash
# 1. Configure ~/.hermes/config.yaml (baseado em hermes/config.yaml.example)
# 2. Defina MCP_GATEWAY_KEY no Portainer (variável da stack)
# 3. No NPM, crie Proxy Host para mcp-gateway:8080
# 4. Execute agente
hermes run --profile agendador
```

Perfis disponíveis em `hermes/profiles/` (usam `gateway` toolset):
- `agendador.yaml`
- `financeiro.yaml`
- `notificador.yaml`
- `orquestrador.yaml`

Configuração do Gateway em `hermes/config.yaml.example`:
```yaml
gateway:
  base_url: "https://mcp.seudominio.com"
  timeout: 30
  headers:
    X-Gateway-Key: "${MCP_GATEWAY_KEY}"
```

---

## Modelo de Dados (Resumo)

```
User → Appointment (1:N)
Service → ProfessionalService ← Professional
Professional → Availability (1:N)
Professional → Appointment (1:N)
Service → Appointment (1:N)
Appointment → Payment (1:1)
WebhookEvent (tabela de idempotência para webhooks)
```

---

## Operação segura

- Clientes da API devem enviar `Authorization: Bearer <API_KEY>`
- Painel `/admin` aceita **duas formas**: header `X-Admin-Key: <ADMIN_API_KEY>` **ou** HTTP Basic (username ignorado, senha = `ADMIN_API_KEY`)
- Em produção, a documentação interativa é desativada e `/metrics` também exige Bearer. `/health` indica vida do processo e `/ready` confirma acesso ao PostgreSQL.
- O sandbox atual do Asaas é `https://api-sandbox.asaas.com/v3` e a produção usa `https://api.asaas.com/v3`. Clientes e cobranças usam referências externas estáveis para reconciliação.
- Horários sem offset são interpretados em `APP_TIMEZONE=America/Sao_Paulo`; reservas não pagas vencidas liberam automaticamente o slot.
- Em produção, o Hermes usa exclusivamente o domínio do MCP Gateway com `X-Gateway-Key`; o gateway injeta o Bearer interno da API e `/ready` confirma o upstream.
- A CI executa testes no PostgreSQL, migrações, Ruff e MyPy antes de publicar as imagens principal, `-backup` e `-mcp-gateway`. A migração aborta se já existirem agendamentos ativos sobrepostos.
- Após cada publicação, valide `/ready` da API, `/ready` do gateway, `tools/list` pelo gateway e o backup mais recente. Faça um teste de restauração periodicamente em ambiente isolado.

## Deploy com Portainer

- Para a variante com PostgreSQL local e Nginx Proxy Manager, siga [DEPLOY_PORTAINER_NPM.md](DEPLOY_PORTAINER_NPM.md).
- Para a topologia com PostgreSQL externo no Neon, siga [DEPLOY_PORTAINER_NEON.md](DEPLOY_PORTAINER_NEON.md).

## Licença

Projeto privado — Plataforma Atende Agenda.
