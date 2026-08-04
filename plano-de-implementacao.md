# Plano de Implantação - Plataforma Atende Agenda

## Visão Geral
Implantação em VPS com Docker Compose, Nginx reverse proxy, HTTPS automático, Hermes Agent integrado via MCP, e Asaas em produção.

---

## Fase 1: Preparação da VPS (Infraestrutura Base)

### 1.1 Provisionamento Inicial
- **SO**: Ubuntu 22.04/24.04 LTS
- **Usuário não-root** com sudo (`deploy` ou similar)
- **SSH hardening**: key-only auth, disable root login, fail2ban
- **Firewall**: UFW - portas 22 (SSH), 80/443 (HTTP/HTTPS), 5432 (Postgres - apenas local/Docker)

### 1.2 Domínio e DNS
- Configurar `A record` → IP da VPS
- Subdomínios sugeridos:
  - `api.seudominio.com` → API FastAPI
  - `hermes.seudominio.com` → (opcional) painel Hermes
- **SSL**: Certbot/Let's Encrypt via Nginx

### 1.3 Dependências Base
```bash
# Docker Engine + Compose plugin
# Git, curl, htop, ufw, fail2ban
```

---

## Fase 2: Banco de Dados (PostgreSQL)

### Opção A: Docker Compose Local (Recomendado p/ início)
- Mesmo `docker-compose.yml` do projeto, mas em `/opt/agenda-atende/`
- Volume persistente `pgdata`
- Backup automático via `pg_dump` + cron/rclone para S3/Wasabi

### Opção B: Gerenciado (RDS, Neon, Supabase)
- Menor ops, maior custo
- Requer apenas `DATABASE_URL` no `.env`

> **Decisão**: Comece com **Opção A** (local). Migre para gerenciado se escala exigir.

---

## Fase 3: Configuração da Aplicação

### 3.1 Estrutura de Diretórios na VPS
```
/opt/agenda-atende/
├── docker-compose.yml      # Orquestração completa
├── .env                    # Segredos (NÃO versionado)
├── nginx/
│   └── nginx.conf          # Reverse proxy + SSL
├── backups/                # Dumps automáticos
└── logs/                   # Logs agregados (opcional: Loki)
```

### 3.2 Arquivo `.env` de Produção
```env
# App
DATABASE_URL=postgresql://agenda_user:SENHA_FORTE@postgres:5432/agenda_atende
API_KEY=CHAVE_LONGA_ALEATORIA_64_CHARS
APP_NAME=Agenda Atende
DEBUG=false

# Asaas PRODUÇÃO
ASAAS_API_KEY=asaas_prod_key
ASAAS_BASE_URL=https://api.asaas.com/api/v3
ASAAS_WEBHOOK_TOKEN=TOKEN_WEBHOOK_SEGURO

# Opcional: Sentry, Logtail, etc.
```

### 3.3 `docker-compose.yml` de Produção
```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: agenda_atende_pg
    environment:
      POSTGRES_USER: agenda_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: agenda_atende
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agenda_user -d agenda_atende"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build: .
    container_name: agenda_atende_api
    environment:
      - DATABASE_URL=postgresql://agenda_user:${POSTGRES_PASSWORD}@postgres:5432/agenda_atende
      - API_KEY=${API_KEY}
      - APP_NAME=${APP_NAME}
      - DEBUG=false
      - ASAAS_API_KEY=${ASAAS_API_KEY}
      - ASAAS_BASE_URL=${ASAAS_BASE_URL}
      - ASAAS_WEBHOOK_TOKEN=${ASAAS_WEBHOOK_TOKEN}
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    expose:
      - "8000"

  nginx:
    image: nginx:alpine
    container_name: agenda_atende_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certbot/conf:/etc/letsencrypt:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - api
    restart: unless-stopped

  certbot:
    image: certbot/certbot
    volumes:
      - ./certbot/conf:/etc/letsencrypt
      - ./certbot/www:/var/www/certbot
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done'"

volumes:
  pgdata:
```

### 3.4 `nginx/nginx.conf` (Reverse Proxy + SSL)
```nginx
events { worker_connections 1024; }

http {
    upstream api_backend {
        server api:8000;
    }

    server {
        listen 80;
        server_name api.seudominio.com;
        location /.well-known/acme-challenge/ { root /var/www/certbot; }
        location / { return 301 https://$host$request_uri; }
    }

    server {
        listen 443 ssl http2;
        server_name api.seudominio.com;

        ssl_certificate /etc/letsencrypt/live/api.seudominio.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/api.seudominio.com/privkey.pem;

        # SSL hardening
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Rate limiting
        limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

        location / {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Webhooks - sem rate limit estrito (Asaas retry)
        location /webhooks/ {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # MCP - auth via header, manter timeout maior
        location /mcp {
            proxy_pass http://api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 300s;
        }
    }
}
```

---

## Fase 4: Deploy Inicial (Primeira Subida)

### 4.1 Na VPS
```bash
# 1. Clonar repo
git clone https://github.com/cezaralfredo/plataforma_atende_agenda /opt/agenda-atende
cd /opt/agenda-atende

# 2. Criar .env de produção (editor de texto)
cp .env.example .env  # criar .env.example no repo antes
vim .env

# 3. Gerar senhas/keys fortes
openssl rand -base64 32  # para API_KEY, POSTGRES_PASSWORD, ASAAS_WEBHOOK_TOKEN

# 4. Subir stack
docker compose up -d --build

# 5. Executar migrações
docker compose exec api alembic upgrade head

# 6. Verificar saúde
curl https://api.seudominio.com/health
```

### 4.2 Certificado SSL Inicial
```bash
# Após DNS propagado
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d api.seudominio.com \
  --email seu@email.com --agree-tos --no-eff-email

docker compose reload nginx
```

---

## Fase 5: Asaas - Configuração Produção

1. **Conta Asaas verificada** (KYC completo)
2. **API Key Produção** → `ASAAS_API_KEY`
3. **Webhook URL**: `https://api.seudominio.com/webhooks/asaas`
4. **Eventos**: `PAYMENT_RECEIVED`, `PAYMENT_CONFIRMED`, `PAYMENT_OVERDUE`, `PAYMENT_REFUNDED`, `PAYMENT_CANCELLED`
5. **Webhook Token** → `ASAAS_WEBHOOK_TOKEN` (mesmo valor no Asaas e `.env`)
6. **Teste**: Sandbox → Produção (valide fluxo PIX/boleto ponta a ponta)

---

## Fase 6: Hermes Agent - Integração MCP

### 6.1 Na VPS (ou máquina separada)
```bash
# Instalar Hermes (ver docs oficiais)
# Configurar ~/.hermes/config.yaml
```

### 6.2 `~/.hermes/config.yaml`
```yaml
mcp_servers:
  agenda_atende:
    url: "https://api.seudominio.com/mcp"
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
      # provider: "whatsapp-web.js"  # ou Evolution API, n8n, Twilio
      # session_path: "./whatsapp-session"
```

### 6.3 Variáveis de Ambiente Hermes
```bash
export AGENDA_API_KEY="sua-api-key-producao"
export WHATSAPP_PROVIDER="evolution"  # ou outro
```

### 6.4 Perfis (já existem em `hermes/profiles/`)
- `agendador.yaml` - consultas/criação reservas
- `financeiro.yaml` - cobranças/verificação pagamentos
- `notificador.yaml` - WhatsApp/notificações
- `orquestrador.yaml` - coordenação

### 6.5 Executar Agentes
```bash
# Terminal 1 - Orquestrador
hermes run --profile orquestrador

# Terminal 2 - Agendador
hermes run --profile agendador

# Terminal 3 - Financeiro
hermes run --profile financeiro

# Terminal 4 - Notificador
hermes run --profile notificador
```

> **Produção**: Use `systemd` ou `supervisor` para daemonizar cada agente.

---

## Fase 7: CI/CD (GitHub Actions)

### `.github/workflows/deploy.yml`
```yaml
name: Deploy Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U test -d test_db"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: alembic upgrade head
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test_db
      - run: pytest tests/ -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /opt/agenda-atende
            git pull origin main
            docker compose up -d --build
            docker compose exec -T api alembic upgrade head
            docker compose exec -T api pytest tests/ -v --tb=short
```

### Secrets GitHub (Settings → Secrets)
- `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`

---

## Fase 8: Observabilidade & Manutenção

### 8.1 Logs
- **Loki + Promtail** (Docker) ou **Logtail/Vector**
- Retenção: 30 dias

### 8.2 Métricas
- **Prometheus** + **Grafana** (Dashboards: API latency, DB connections, HTTP errors, Asaas webhook success rate)
- `prometheus.yml` scrape `api:8000/metrics` (adicionar `prometheus-fastapi-instrumentator`)

### 8.3 Health Checks Automatizados
- Cron a cada 5min: `curl -f https://api.seudominio.com/health || alert`
- Uptime Kuma / Better Uptime / PagerDuty

### 8.4 Backup Automático
```bash
# /opt/agenda-atende/backup.sh (cron daily 03:00)
#!/bin/bash
docker compose exec -T postgres pg_dump -U agenda_user agenda_atende | gzip > /opt/agenda-atende/backups/agenda_$(date +%F).sql.gz
# Opcional: rclone copy to S3/Wasabi/GDrive
find /opt/agenda-atende/backups -mtime +30 -delete
```

### 8.5 Atualizações de Segurança
- `unattended-upgrades` no Ubuntu
- `docker compose pull && docker compose up -d` mensal (imagens base)
- Renovação SSL: Certbot auto-renew (já configurado)

---

## Fase 9: Checklist de Go-Live

| Item | Status |
|------|--------|
| VPS provisionada + hardening | ☐ |
| DNS + SSL válido | ☐ |
| PostgreSQL rodando + migrações aplicadas | ☐ |
| API respondendo em `https://api.seudominio.com/health` | ☐ |
| Docs Swagger acessíveis (`/docs`) | ☐ |
| Asaas webhook recebendo eventos (teste real) | ☐ |
| Pagamento PIX/boleto ponta a ponta validado | ☐ |
| Hermes agentes conectando no MCP | ☐ |
| WhatsApp/Evolution API enviando msgs teste | ☐ |
| CI/CD deployando em push main | ☐ |
| Backup automático funcionando (restore testado) | ☐ |
| Monitoramento/alertas ativos | ☐ |
| Documentação de runbook (rollback, incidentes) | ☐ |

---

## Estimativa de Esforço

| Fase | Tempo (pessoa) |
|------|----------------|
| 1-2: VPS + DB | 2-4h |
| 3-4: App + Nginx + SSL | 3-5h |
| 5: Asaas produção | 1-2h |
| 6: Hermes + Agentes | 2-4h |
| 7: CI/CD | 1-2h |
| 8: Observabilidade | 2-3h |
| 9: Testes + Go-live | 2-4h |
| **Total** | **~15-24h** |

---

## Próximos Passos Sugeridos

1. **Criar `.env.example` no repo** (template sem segredos)
2. **Adicionar `Dockerfile`** na raiz (multi-stage build para imagem menor)
3. **Configurar secrets no GitHub Actions**
4. **Provisionar VPS** e validar conectividade
5. **Executar Fase 1-4** em sequência

---

## Perguntas para Alinhar

1. **Já tem domínio configurado?** (SSL depende disso)
2. **Vai usar PostgreSQL local (Docker) ou gerenciado?**
3. **Provedor WhatsApp**: Evolution API, WhatsApp Web.js, Twilio, n8n?
4. **Hermes roda na mesma VPS ou máquina separada?**
5. **Já tem conta Asaas verificada (KYC) para produção?**
6. **Precisa de Sentry/Error tracking desde o dia 1?**
7. **Qual estratégia de backup offsite?** (S3, Wasabi, GDrive, outro)