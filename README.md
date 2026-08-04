# Plataforma Atende Agenda

API REST completa para gestão de agendamentos, profissionais, serviços e pagamentos — construída com **FastAPI**, **SQLAlchemy** e **PostgreSQL**. Inclui integração com **Asaas** para pagamentos e suporte a **MCP (Model Context Protocol)** para agentes de IA.

---

## Funcionalidades Principais

### Gestão de Usuários
- CRUD completo de usuários (clientes)
- Busca por telefone com validação de duplicidade

### Gestão de Profissionais
- CRUD de profissionais (prestadores de serviço)
- Associação a usuários do sistema
- Filtro por profissionais ativos/inativos

### Gestão de Serviços
- CRUD de serviços oferecidos
- Categorização de serviços
- Vinculação a profissionais
- Duração e preço configuráveis

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
  - `listar_servicos`
  - `verificar_disponibilidade`
  - `criar_reserva`
  - `cancelar_reserva`
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
│   │   └── user.py
│   ├── repositories/     # Camada de acesso a dados
│   │   ├── appointment_repo.py
│   │   ├── availability_repo.py
│   │   ├── base.py
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
│       ├── professional_service.py
│       └── service_service.py
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
DATABASE_URL=postgresql://agenda_user:agenda_pass@localhost:5432/agenda_atende
API_KEY=sua-chave-secreta-aqui
APP_NAME=Agenda Atende
DEBUG=true

ASAAS_API_KEY=sua-chave-asaas
ASAAS_BASE_URL=https://sandbox.asaas.com/api/v3
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

### Configuração do Cliente MCP
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
| `listar_servicos` | Lista serviços com filtros opcionais |
| `verificar_disponibilidade` | Verifica horários livres de um profissional em uma data |
| `criar_reserva` | Cria agendamento (valida disponibilidade) |
| `cancelar_reserva` | Cancela agendamento existente |

### Hermes (Orquestração de Agentes)
```bash
# Instalar Hermes (se disponível)
# Configurar ~/.hermes/config.yaml baseado em hermes/config.yaml
# Executar agente
hermes run --profile agendador
```

Perfis disponíveis em `hermes/profiles/`:
- `agendador.yaml`
- `financeiro.yaml`
- `notificador.yaml`
- `orquestrador.yaml`

---

## Modelo de Dados (Resumo)

```
User ←→ Professional (1:1)
Professional → Service (1:N)
Professional → Availability (1:N)
Service → Appointment (1:N)
User → Appointment (1:N)
Appointment → Payment (1:1)
```

---

## Licença

Projeto privado — Plataforma Atende Agenda.