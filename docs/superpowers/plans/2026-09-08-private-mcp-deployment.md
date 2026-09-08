# Private MCP Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Hermes-to-Agenda MCP traffic private, rotate the compromised API credential, and make Portainer deployments traceable by immutable image tag.

**Architecture:** The API joins a named external Docker network shared with the Hermes stack; Hermes resolves `agenda-api` there and calls `http://agenda-api:8000/mcp`. Nginx Proxy Manager continues to serve public API routes but explicitly rejects `/mcp`. The API image tag is required by every Portainer manifest, while keys remain only in Portainer/Hermes secret configuration.

**Tech Stack:** Docker Compose/Portainer CE, Nginx Proxy Manager, FastAPI, pytest, PyYAML, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-08-mcp-private-security-design.md`

## Global Constraints

- Base all implementation work on a clean worktree created from `origin/master`; do not alter or stage the pre-existing local changes.
- Do not write, print, commit, test-fixture, or document any real secret.
- Keep `/mcp` exclusively reachable from `agenda_mcp_internal`; public NPM traffic to that path must receive a rejection.
- Require an immutable `IMAGE_TAG` in both Portainer compose manifests; do not use `latest`.
- Do not add an MCP gateway container.
- Preserve API routes other than `/mcp`, the existing NPM alias `agenda-api`, and the health endpoints.

---

## File Structure

- `docker-compose.portainer-neon.yml` — API stack for Neon; adds the external private MCP network and requires a tag.
- `docker-compose.portainer-npm.yml` — API plus local PostgreSQL stack; adds the same private MCP network and requires a tag.
- `.env.hermes.example` — secret-free example of Hermes MCP URL and variable names.
- `docs/DOC-RESOLUCAO-MCP-AUTH.md` — replaces historical credential material with a safe rotation record.
- `docs/OPERACAO_MCP_PRIVADO.md` — repeatable Portainer/NPM/Hermes operational procedure and verification commands.
- `tests/test_deployment_config.py` — executable contract for image tags and network declarations.

### Task 1: Enforce the private-network and immutable-image compose contract

**Files:**
- Modify: `docker-compose.portainer-neon.yml`
- Modify: `docker-compose.portainer-npm.yml`
- Modify: `tests/test_deployment_config.py`

**Interfaces:**
- Consumes: Portainer variables `IMAGE_TAG`, `NPM_NETWORK`, and optional `AGENDA_MCP_NETWORK`.
- Produces: API service network alias `agenda-api` on the external network named by `${AGENDA_MCP_NETWORK:-agenda_mcp_internal}`.

- [ ] **Step 1: Write failing compose-contract tests**

Add assertions for both manifests:

```python
def test_portainer_manifests_require_immutable_image_tags():
    for path in ("docker-compose.portainer-neon.yml", "docker-compose.portainer-npm.yml"):
        image = _yaml(path)["services"]["api"]["image"]
        assert "${IMAGE_TAG:?Defina IMAGE_TAG no Portainer}" in image
        assert ":latest" not in image


def test_portainer_api_joins_the_shared_private_mcp_network():
    for path in ("docker-compose.portainer-neon.yml", "docker-compose.portainer-npm.yml"):
        compose = _yaml(path)
        assert "mcp_internal" in compose["services"]["api"]["networks"]
        assert compose["networks"]["mcp_internal"] == {
            "external": True,
            "name": "${AGENDA_MCP_NETWORK:-agenda_mcp_internal}",
        }
```

- [ ] **Step 2: Run the new tests and verify failure**

Run: `pytest tests/test_deployment_config.py -q`

Expected: the NPM manifest test fails because it still references `latest`, and both network assertions fail.

- [ ] **Step 3: Make the smallest manifest changes**

Use this image expression in both API services and add `mcp_internal` to their networks:

```yaml
image: "${REGISTRY:-ghcr.io}/${GITHUB_REPOSITORY:-cezaralfredo/plataforma_atende_agenda}:${IMAGE_TAG:?Defina IMAGE_TAG no Portainer}"
networks:
  npm:
    aliases:
      - agenda-api
  mcp_internal:
```

For each compose file, declare:

```yaml
networks:
  mcp_internal:
    external: true
    name: "${AGENDA_MCP_NETWORK:-agenda_mcp_internal}"
```

Keep the existing `agenda_internal` network in the NPM/PostgreSQL stack unchanged.

- [ ] **Step 4: Verify tests and rendered compose configuration**

Run:

```bash
pytest tests/test_deployment_config.py -q
IMAGE_TAG=verify DATABASE_URL=postgresql+psycopg://user:pass@db/db API_KEY=verify ADMIN_API_KEY=verify ASAAS_API_KEY=verify ASAAS_WEBHOOK_TOKEN=verify docker compose -f docker-compose.portainer-neon.yml config
IMAGE_TAG=verify POSTGRES_PASSWORD=verify API_KEY=verify ADMIN_API_KEY=verify ASAAS_API_KEY=verify ASAAS_WEBHOOK_TOKEN=verify docker compose -f docker-compose.portainer-npm.yml config
```

Expected: all deployment tests pass and each rendered API service has `agenda_mcp_internal` plus its existing network.

- [ ] **Step 5: Commit the compose contract**

```bash
git add docker-compose.portainer-neon.yml docker-compose.portainer-npm.yml tests/test_deployment_config.py
git commit -m "fix(deploy): make MCP network private and images immutable"
```

### Task 2: Replace unsafe configuration documentation with a repeatable operational runbook

**Files:**
- Modify: `.env.hermes.example`
- Modify: `docs/DOC-RESOLUCAO-MCP-AUTH.md`
- Create: `docs/OPERACAO_MCP_PRIVADO.md`
- Modify: `tests/test_deployment_config.py`

**Interfaces:**
- Consumes: `MCP_ATENDE_AGENDA_URL`, `MCP_ATENDE_AGENDA_API_KEY`, `AGENDA_MCP_NETWORK`, and the API service DNS name `agenda-api`.
- Produces: safe, secret-free instructions for creating the shared Docker network, updating Hermes, blocking the NPM path, rotating one key, and validating the result.

- [ ] **Step 1: Write failing documentation-safety tests**

Add tests that enforce the new public contract without inspecting values:

```python
def test_hermes_example_uses_only_the_internal_mcp_url():
    example = Path(".env.hermes.example").read_text(encoding="utf-8")
    assert "MCP_ATENDE_AGENDA_URL=http://agenda-api:8000/mcp" in example
    assert "MCP_ATENDE_AGENDA_API_KEY=" in example
    assert "agenda.anauedesign.com.br/mcp" not in example


def test_mcp_resolution_document_does_not_embed_a_real_bearer_value():
    document = Path("docs/DOC-RESOLUCAO-MCP-AUTH.md").read_text(encoding="utf-8")
    assert "Nova chave (definitiva)" not in document
    assert "Authorization: Bearer <API_KEY>" in document
```

- [ ] **Step 2: Run the documentation tests and verify failure**

Run: `pytest tests/test_deployment_config.py -q`

Expected: the internal Hermes URL and safe resolution-document assertions fail.

- [ ] **Step 3: Update examples and documentation without values**

Replace the old Hermes variable with this exact example block:

```dotenv
MCP_ATENDE_AGENDA_URL=http://agenda-api:8000/mcp
MCP_ATENDE_AGENDA_API_KEY=SUA_CHAVE_GERADA_FORA_DO_REPOSITORIO
```

Replace the resolution document's credential section with `<API_KEY>` placeholders only. Create `docs/OPERACAO_MCP_PRIVADO.md` containing these exact operational checkpoints:

```text
1. Create Docker network agenda_mcp_internal as an attachable bridge network.
2. Declare the same external network in both Portainer stacks.
3. Set Hermes MCP_ATENDE_AGENDA_URL to http://agenda-api:8000/mcp.
4. Set the same newly generated key only in API_KEY and MCP_ATENDE_AGENDA_API_KEY.
5. Add NPM advanced configuration: location = /mcp { return 404; }.
6. Recreate the API and restart Hermes gateways.
7. Validate initialize and tools/list from Hermes, then inspect only new API logs.
```

Include safe commands that reference variable names but never expand or print their values.

- [ ] **Step 4: Verify documentation tests and secret scan**

Run:

```bash
pytest tests/test_deployment_config.py -q
git grep -n -E 'Bearer [A-Za-z0-9+/]{32,}={0,2}' -- ':!docs/superpowers/plans/*'
```

Expected: tests pass and the scan returns no tracked hard-coded bearer credential. If it finds a value, remove it before continuing.

- [ ] **Step 5: Commit safe operational documentation**

```bash
git add .env.hermes.example docs/DOC-RESOLUCAO-MCP-AUTH.md docs/OPERACAO_MCP_PRIVADO.md tests/test_deployment_config.py
git commit -m "docs: document private Hermes MCP operation"
```

### Task 3: Apply the controlled production rotation and validate the private route

**Files:**
- Modify operational state only: Portainer API stack variables, Hermes active profile/environment, Hermes stack network attachment, and NPM advanced configuration.
- Reference: `docs/OPERACAO_MCP_PRIVADO.md`

**Interfaces:**
- Consumes: the verified immutable image tag from GitHub Actions and a newly generated key held by the operator.
- Produces: Hermes `initialize` and `tools/list` requests over `agenda_mcp_internal` with HTTP `200`.

- [ ] **Step 1: Capture a redacted pre-change baseline**

Run on the VPS without printing environment values:

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
sudo docker inspect atende_agenda-api-1 hermes --format '{{.Name}} {{range $n,$v := .NetworkSettings.Networks}}{{$n}}={{$v.IPAddress}} {{end}}'
sudo docker logs --since 15m atende_agenda-api-1 2>&1 | grep -E 'POST /mcp|GET /ready' | tail -100
```

Expected: baseline identifies the running image and current networks without exposing credentials.

- [ ] **Step 2: Create and declare the shared network**

Run once on the VPS:

```bash
sudo docker network inspect agenda_mcp_internal >/dev/null 2>&1 || sudo docker network create --driver bridge --attachable agenda_mcp_internal
sudo docker network inspect agenda_mcp_internal --format '{{.Name}} {{range .Containers}}{{.Name}} {{end}}'
```

Expected: the network exists. Update both Portainer stacks to declare `AGENDA_MCP_NETWORK=agenda_mcp_internal`; deploy the API stack using the verified immutable image tag; then deploy or attach the Hermes stack using the same external network.

- [ ] **Step 3: Rotate credentials and internal endpoint as one controlled change**

In Portainer, set the new randomly generated value as `API_KEY`; in Hermes, set that same value as `MCP_ATENDE_AGENDA_API_KEY` and set `MCP_ATENDE_AGENDA_URL=http://agenda-api:8000/mcp`. Do not paste either value into a shell history, ticket, commit, or chat. Recreate the API, then restart the Hermes gateway services so their environment reloads.

- [ ] **Step 4: Block the public MCP path and validate from Hermes**

Add this NPM advanced configuration to the public Agenda host, then save/reload it:

```nginx
location = /mcp {
    return 404;
}
```

Run an authenticated MCP `initialize` and `tools/list` using the existing Hermes client configuration. Confirm the requests in API logs come from the private Docker network; confirm an unauthenticated public `POST /mcp` returns `404`.

- [ ] **Step 5: Observe and record the rollout result**

After the agreed observation window, run:

```bash
sudo docker logs --since 30m atende_agenda-api-1 2>&1 | grep 'POST /mcp' | tail -100
sudo docker inspect atende_agenda-api-1 hermes --format '{{.Name}} {{range $n,$v := .NetworkSettings.Networks}}{{$n}}={{$v.IPAddress}} {{end}}'
```

Expected: Hermes-originated calls are `200`, `/ready` remains `200`, and both services list `agenda_mcp_internal`.

### Task 4: Validate the production-ready branch before review

**Files:**
- Verify: all files changed by Tasks 1–2.

- [ ] **Step 1: Run the focused tests**

Run: `pytest tests/test_deployment_config.py -q`

Expected: PASS.

- [ ] **Step 2: Run the full local quality gate**

Run:

```bash
ruff check app/ tests/
mypy app/ --ignore-missing-imports
pytest tests/ -q
```

Expected: all commands exit `0`.

- [ ] **Step 3: Check the review diff excludes secrets and unrelated edits**

Run:

```bash
git diff origin/master...HEAD --check
git diff --name-only origin/master...HEAD
git grep -n -E 'Bearer [A-Za-z0-9+/]{32,}={0,2}' -- ':!docs/superpowers/plans/*'
```

Expected: whitespace check passes, only plan-scoped paths changed, and no bearer secret is tracked.

- [ ] **Step 4: Request review and publish only after approval**

```bash
git push -u origin codex/private-mcp-deployment
gh pr create --base master --head codex/private-mcp-deployment --title "Harden private MCP deployment" --fill
```

Expected: a reviewable pull request contains the manifest, documentation, and test changes; production deployment occurs only after the merge and approval checkpoint.
