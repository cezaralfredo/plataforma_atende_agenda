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
```

`NPM_NETWORK` já usa como padrão a rede encontrada nesta VPS. Só a altere se a rede do Nginx Proxy Manager mudar.

## Após o deploy

No Nginx Proxy Manager, crie um **Proxy Host**:

- Domain Names: `api.seudominio.com`
- Scheme: `http`
- Forward Hostname / IP: `agenda-api`
- Forward Port: `8000`
- SSL: solicite um novo certificado Let's Encrypt e force SSL.

Em seguida, valide `https://api.seudominio.com/health`. Para o navegador e o painel administrativo em `https://api.seudominio.com/admin`, a recomendação é autenticação HTTP Basic, usando `ADMIN_API_KEY` como senha. `X-Admin-Key` permanece somente como compatibilidade legada para clientes de máquina; não é a orientação para acesso pelo navegador.

## Limitações deliberadas

Esta Stack não publica as portas 80 e 443, pois elas já pertencem ao Nginx Proxy Manager. Ela também usa variáveis de ambiente em vez de Docker secrets, porque o ambiente atual não opera em Docker Swarm.
