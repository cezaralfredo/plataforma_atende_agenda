# Deploy no Portainer Community Edition com Nginx Proxy Manager e Neon

> Este procedimento altera somente a topologia com banco PostgreSQL externo. Não execute nenhuma ação no Portainer sem a janela de mudança aprovada.

Use exclusivamente `docker-compose.portainer-neon.yml` para a topologia externa Neon. A variante com PostgreSQL local permanece documentada em [DEPLOY_PORTAINER_NPM.md](DEPLOY_PORTAINER_NPM.md).

## Pré-requisitos de mudança

1. Obtenha `IMAGE_TAG` a partir do build de imagem bem-sucedido na branch `master`; não use `latest`.
2. Verifique que existe um backup ou ponto de restauração do Neon antes de mudar a Stack.
3. Crie primeiro uma credencial de substituição para o banco e mantenha a credencial anterior válida durante todo o rollout.
4. Não remova o volume PostgreSQL antigo durante este rollout.

## Variáveis da Stack

No Portainer, crie ou atualize as variáveis na tabela de ambiente da Stack. Informe `DATABASE_URL` somente nessa tabela, nunca embutida no editor do Compose. O valor de `DATABASE_URL` deve começar exatamente com `postgresql+psycopg://`, pois a aplicação usa Psycopg 3.

Cadastre os valores obrigatórios: `IMAGE_TAG`, `DATABASE_URL`, `API_KEY`, `ADMIN_API_KEY`, `ASAAS_API_KEY` e `ASAAS_WEBHOOK_TOKEN`.

Quando necessário, ajuste os valores opcionais: `REGISTRY`, `GITHUB_REPOSITORY`, `APP_NAME`, `APP_TIMEZONE`, `ASAAS_BASE_URL` e `NPM_NETWORK`.

O Docker Standalone não protege variáveis de ambiente como Docker secrets: seus valores permanecem visíveis para administradores do Portainer e por inspeção do container. Controle o acesso administrativo e faça a rotação de credenciais após a mudança.

## Deploy e validação

1. Crie ou atualize a Stack usando `docker-compose.portainer-neon.yml` e as variáveis já cadastradas.
2. Confirme a conclusão das migrações no log inicial do container.
3. No Nginx Proxy Manager, mantenha o Proxy Host apontando para `agenda-api` na porta `8000` pela rede externa `npm`.
4. Valide `/ready`, autenticação da API, MCP, pagamentos e webhooks antes de encerrar a mudança.

## Rollback

Se a validação falhar, restaure o `IMAGE_TAG` anterior e a configuração anterior da Stack. Mantenha o volume PostgreSQL antigo intacto; ele é proibido de ser removido durante este rollout.
