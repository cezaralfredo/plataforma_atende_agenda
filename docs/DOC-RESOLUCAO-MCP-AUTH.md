# Resolução — Falha de Autenticação do endpoint `/mcp` (HTTP 401)

> **Data:** 2026-08-23 · **Responsável:** Orquestrador (anauedesign) · **Status:** Em validação pós-deploy

---

## 1. Diagnóstico

O gateway Hermes (orquestrador) recebia **HTTP 401 Unauthorized** ao conectar no
servidor MCP `https://agenda.anauedesign.com.br/mcp` (estado `parked`).

### Causa raiz (código)

Arquivo `app/mcp/router.py`, função `verify_auth`:

```python
def verify_auth(request: FastAPIRequest):
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.api_key}"   # comparação EXATA (==)
    if auth != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

- O header `Authorization` precisa ser **idêntico** a `Bearer {settings.api_key}`.
- `settings.api_key` é carregado de:
  1. **Portainer** — variável `API_KEY` da Stack (deploy `docker-compose.portainer-npm.yml`, serviço `api`) ✅ *fonte real em produção*
  2. Arquivo `.env` do repositório (padrão `dev-api-key-change-in-production`) — fallback.

### Diagnóstico dos valores em conflito

| Fonte | Valor (redigido) | Comprimento |
|-------|-------------------|-------------|
| Processo orquestrador ativo (antes) | `3y8K****` | 32 |
| `.env` profile orquestrador (antes) | `3y8K****` | 32 |
| `.env` global `/opt/data/.env` (antes) | `ptr_****` | 34 |
| Servidor (`settings.api_key` no Portainer) | *(deve bater com o cliente)* | — |

Havia **3 valores diferentes** — por isso o 401 (o servidor não reconhecia a chave do cliente).

---

## 2. Solução aplicada

Padronizar **UMA única chave forte** em todos os pontos sob nosso controle.

### Nova chave (definitiva)
```
gUzbH90YBcbIvY6yvE5Epm8X0Vzsp2gw7y1QJVH/hmM=
```
Gerada com `openssl rand -base64 32` (44 chars). Guarde em local seguro (ex.: cofre).

### 2.1 Lado cliente (orquestrador) — APLICADO
Chave alinhada nos dois arquivos de ambiente do orquestrador:
- `/opt/data/profiles/orquestrador/.env` → `MCP_ATENDE_AGENDA_API_KEY=gUzbH90YBcbIvY6yvE5Epm8X0Vzsp2gw7y1QJVH/hmM=`
- `/opt/data/.env` → mesmo valor

Backups criados:
- `/opt/data/profiles/orquestrador/.env.bak-20260823-150651`
- `/opt/data/.env.bak-20260823-150651`

### 2.2 Lado servidor (Portainer) — APLICADO PELO TI
No Portainer, na Stack que roda o serviço `api`, na seção **Environment variables**,
definir/alterar a variável:

```
API_KEY = gUzbH90YBcbIvY6yvE5Epm8X0Vzsp2gw7y1QJVH/hmM=
```

E **recrear/atualizar** o container `api` para que o `settings.api_key` reflita o novo valor.

---

## 3. Reinício do gateway Hermes (orquestrador) — PENDENTE

Para o processo do orquestrador **enviar a nova chave** no header `Authorization`,
o gateway precisa recarregar o `.env`. O processo ativo roda sob **s6 supervisionado**
(`gateway-orquestrador`, PID base). Reiniciar derruba a sessão TUI ativa — fazer com
conscientização:

```bash
# identificar o processo
ps aux | grep hermes | grep -v grep

# reiniciar o serviço supervisionado (via s6)
s6-svc -r /run/service/gateway-orquestrador   # ou conforme layout do serviço
```

Após o restart, o `.env` recarregado carrega a nova chave.

---

## 4. Validação final (pós-deploy)

Após alinhar Portainer + reiniciar orquestrador, validar a conexão real do MCP:

```python
import urllib.request, json
key = open('/opt/data/profiles/orquestrador/.env').read()  # ler a chave
payload = json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize",
    "params":{"protocolVersion":"2024-11-05","capabilities":{},
    "clientInfo":{"name":"orquestrador","version":"1.0"}}}).encode()
req = urllib.request.Request("https://agenda.anauedesign.com.br/mcp",
    data=payload, method="POST",
    headers={"Content-Type":"application/json",
             "Authorization":f"Bearer {chave}"})
import urllib.error
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("✅ MCP OK:", r.status, r.read().decode()[:200])
except urllib.error.HTTPError as e:
    print("❌ MCP FALHOU:", e.code, e.read().decode()[:200])
```

Esperado: **200** no `initialize` (antes dava 401).

---

## 5. Roteiro (recapitulativo)

1. ✅ Gerar chave forte única.
2. ✅ Alinhar `.env` do orquestrador (profile + global) com a chave.
3. ✅ Aplicar `API_KEY` da Stack no Portainer com a mesma chave *(TI)*.
4. ⬜ Recrear container `api` no Portainer (aplicar a nova env).
5. ⬜ Reiniciar `gateway-orquestrador` (carregar nova chave no processo).
6. ⬜ Validar com teste de `initialize` (passo 4) — expectativa 200.
7. ⬜ Confirmar no Hermes que o MCP `Atende Agenda` saiu do estado `parked`.

---

*Documento gerado automaticamente pelo Orquestrador — anauedesign. Sempre guardar a chave
`gUzbH90YBcbIvY6yvE5Epm8X0Vzsp2gw7y1QJVH/hmM=` fora do sistema de controle de versão.*