# Deploy no Portainer Community Edition com Nginx Proxy Manager e PostgreSQL local

> Operação endurecida: aplique migrações antes do tráfego, configure `APP_TIMEZONE`, valide `/ready` e implante também a imagem `-backup`. API e métricas usam Bearer; o painel usa Basic.

Use `docker-compose.portainer-npm.yml` para criar uma nova Stack. Esta é a variante com PostgreSQL local, feita para um Docker comum (sem Swarm) e para o Nginx Proxy Manager já instalado no ambiente. Para a topologia com PostgreSQL externo no Neon, siga [DEPLOY_PORTAINER_NEON.md](DEPLOY_PORTAINER_NEON.md).

## Variáveis da Stack

Cadastre estas variáveis no Portainer antes do deploy:

```env
POSTGRES_PASSWORD=uma-senha-forte-sem-espacos
API_KEY=chave-privada-para-mcp
ADMIN_API_KEY=chave-privada-para-admin
ASAAS_API_KEY=sua-chave-asaas
ASAAS_WEBHOOK_TOKEN=seu-token-de-webhook-asaas
ASAAS_BASE_URL=https://api.asaas.com/v3
APP_NAME=Agenda Atende
REGISTRY=ghcr.io
GITHUB_REPOSITORY=cezaralfredo/plataforma_atende_agenda
NPM_NETWORK=nginx-proxy_default

# MCP Gateway (para Hermes externo)
MCP_GATEWAY_KEY=chave-forte-para-gateway-hermes
```

`NPM_NETWORK` já usa como padrão a rede encontrada nesta VPS. Só a altere se a rede do Nginx Proxy Manager mudar.

## Após o deploy

No Nginx Proxy Manager, crie **dois Proxy Hosts**:

### 1. API Principal
- Domain Names: `api.seudominio.com`
- Scheme: `http`
- Forward Hostname / IP: `agenda-api`
- Forward Port: `8000`
- SSL: solicite um novo certificado Let's Encrypt e force SSL.

### 2. MCP Gateway (para Hermes)
- Domain Names: `mcp.seudominio.com` (ou subdomínio dedicado)
- Scheme: `http`
- Forward Hostname / IP: `mcp-gateway`
- Forward Port: `8080`
- SSL: solicite certificado Let's Encrypt e force SSL.

Em seguida, valide:
- `https://api.seudominio.com/health` — API principal
- `https://mcp.seudominio.com/health` — MCP Gateway

Para o painel administrativo em `https://api.seudominio.com/admin`, use autenticação HTTP Basic com `ADMIN_API_KEY` como senha.

## Hermes + MCP Gateway

1. Configure `~/.hermes/config.yaml` baseado em `hermes/config.yaml.example`:
   ```yaml
   gateway:
     base_url: "https://mcp.seudominio.com"
     headers:
       X-Gateway-Key: "mesmo-valor-do-MCP_GATEWAY_KEY"
   ```

2. Perfis Hermes em `hermes/profiles/` já usam toolset `gateway` (não `mcp_tools`).

3. Execute: `hermes run --profile orquestrador`

## Limitações deliberadas

Esta Stack não publica as portas 80 e 443, pois elas já pertencem ao Nginx Proxy Manager. Ela também usa variáveis de ambiente em vez de Docker secrets, porque o ambiente atual não opera em Docker Swarm.
