# Deploy no Portainer Community Edition com Nginx Proxy Manager

Use `docker-compose.portainer-npm.yml` para criar uma nova Stack. Esta versão foi feita para um Docker comum (sem Swarm) e para o Nginx Proxy Manager já instalado no ambiente.

## Variáveis da Stack

Cadastre estas variáveis no Portainer antes do deploy:

```env
POSTGRES_PASSWORD=uma-senha-forte-sem-espacos
API_KEY=chave-privada-para-mcp
ADMIN_API_KEY=chave-privada-para-admin
ASAAS_API_KEY=sua-chave-asaas
ASAAS_WEBHOOK_TOKEN=seu-token-de-webhook-asaas
ASAAS_BASE_URL=https://api.asaas.com/api/v3
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

Em seguida, valide `https://api.seudominio.com/health`. O painel administrativo usa `https://api.seudominio.com/admin` e continua protegido por `X-Admin-Key`.

## Limitações deliberadas

Esta Stack não publica as portas 80 e 443, pois elas já pertencem ao Nginx Proxy Manager. Ela também usa variáveis de ambiente em vez de Docker secrets, porque o ambiente atual não opera em Docker Swarm.
