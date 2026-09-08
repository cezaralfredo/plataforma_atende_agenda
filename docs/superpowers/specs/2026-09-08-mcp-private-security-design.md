# MCP privado e endurecimento de segurança

**Data:** 2026-09-08  
**Status:** aprovado para planejamento  
**Escopo:** comunicação Hermes–Agenda Atende, rotação de credenciais, deploy rastreável e proteção do painel administrativo.

## Contexto

O Hermes e a API Agenda Atende executam na mesma VPS, mas estavam se comunicando pelo domínio público e pelo proxy reverso. Esse caminho permitiu configurações divergentes de chave, produziu respostas `401` intermitentes e torna um redeploy capaz de desfazer uma correção manual de rede.

Há ainda uma credencial real registrada em documentação versionada. Ela deve ser tratada como comprometida. A cópia de trabalho local diverge da `master` remota e contém modificações sem finalizar; portanto não será usada como base nem publicada.

## Decisões

1. O MCP é exclusivamente interno ao Hermes. Não haverá gateway MCP público nem proxy adicional.
2. Hermes e API compartilharão uma rede Docker externa, com nome estável e declarado nos dois manifests de stack.
3. O Hermes chamará a API pelo nome DNS interno `agenda-api` e porta `8000`; não usará o domínio público.
4. O proxy reverso negará acesso externo a `/mcp`. As demais rotas públicas necessárias continuam inalteradas.
5. A chave de API será substituída por uma nova chave aleatória, mantida apenas nos segredos/configurações operacionais de Portainer e Hermes. Nenhuma chave será incluída em documentação, commits, saídas de teste ou logs.
6. O gateway experimental não será incorporado: ele acrescenta superfície operacional sem benefício para um único consumidor interno.
7. Todo deploy de produção usará uma imagem por tag imutável vinculada ao commit, nunca `latest`.

## Topologia alvo

```text
Hermes ── agenda_mcp_internal ── agenda-api:8000/mcp
                                      │
                                      └── rede do proxy ── rotas públicas da API

Internet ── proxy reverso ── /mcp => bloqueado
```

`agenda_mcp_internal` é criada uma vez na VPS como rede externa e declarada nas duas stacks. A API continua associada à rede do proxy para as rotas públicas, mas a comunicação MCP não atravessa o proxy.

## Rotação controlada

1. Gerar uma nova chave fora do repositório e armazená-la apenas nos campos secretos da stack da API e no ambiente ativo do Hermes.
2. Atualizar os dois lados na mesma janela controlada e recriar a API e os gateways Hermes necessários.
3. Validar o `initialize` do MCP a partir do container Hermes pelo endereço interno.
4. Confirmar que os logs novos do serviço não apresentam `401` para o cliente configurado e que `/ready` continua saudável.
5. Revogar a chave anterior definitivamente. Como uma chave foi exposta em Git, sua remoção do arquivo é acompanhada de rotação; a limpeza do histórico será avaliada conforme a política do repositório privado.

Não será implementada aceitação simultânea da chave antiga: isso prolongaria a validade de uma credencial comprometida.

## Ajustes de código e configuração

### MCP e deploy

- Alterar os manifests Portainer para receber uma tag obrigatória de imagem e para declarar a rede externa privada do MCP.
- Incluir instruções operacionais seguras para conectar a stack Hermes à mesma rede, sem valores secretos.
- Substituir a documentação que contém credencial por instruções de rotação e variáveis de exemplo.
- Adicionar testes de configuração que rejeitem `latest`, validem a rede privada e garantam que nenhum gateway público volte a ser declarado.
- Manter a comparação de credencial em tempo constante e o diagnóstico por identificador não reversível, sem registrar headers de autorização.

### Painel administrativo

- Remover o bootstrap público do primeiro administrador. O primeiro usuário deverá ser provisionado por segredo/ação administrativa controlada, não por uma requisição anônima da internet.
- Validar uma sessão assinada contra o administrador ativo no banco, de modo que desativação ou remoção revogue sessões existentes.
- Enviar cookie `Secure` em produção e preservar `HttpOnly` e `SameSite`.
- Proteger formulários que alteram estado contra requisições forjadas (CSRF) e cobrir o fluxo com testes.

## Fora de escopo

- Alterar regras de negócio de agenda, pagamentos ou integrações Asaas.
- Expor o MCP a agentes externos.
- Migrar a infraestrutura completa de proxy ou banco de dados.

## Critérios de aceite

1. O Hermes executa `initialize` e `tools/list` no endpoint interno e recebe `200`.
2. O proxy público não encaminha `/mcp` para a API.
3. Nenhum `401` novo é gerado pelo Hermes após uma janela de observação definida.
4. API, migrações e `/ready` permanecem saudáveis após recriação.
5. A imagem efetivamente implantada tem tag imutável correspondente a um commit verificado.
6. Não há credenciais reais rastreadas pelo Git nem emitidas por logs de aplicação.
7. Um visitante anônimo não consegue criar o primeiro administrador, e uma sessão de administrador desativado deixa de autorizar o painel.

## Verificação

- Testes unitários e de integração para autenticação MCP, sessões administrativas e manifests de deploy.
- Ruff, MyPy, migrações Alembic e suíte completa em PostgreSQL.
- Build das imagens de produção no CI.
- Checklist pós-deploy com inspeção de redes, health checks e amostragem de logs sem expor segredos.
