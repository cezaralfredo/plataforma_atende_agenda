# Admin Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent anonymous administrator bootstrap, revoke sessions for disabled administrators, secure production cookies, and protect authenticated browser mutations against CSRF.

**Architecture:** The existing signed session cookie gains a per-session CSRF nonce while retaining the existing administrator identifier and expiry. Authorization resolves that identifier against the database on every protected request. The first administrator requires an operator-supplied bootstrap token, and every state-changing authenticated panel form submits a valid CSRF token.

**Tech Stack:** FastAPI dependencies and forms, SQLAlchemy, Jinja2, Python standard-library HMAC/PBKDF2, pytest/httpx.

**Spec:** `docs/superpowers/specs/2026-09-08-mcp-private-security-design.md`

## Global Constraints

- Base all implementation work on a clean worktree created from `origin/master`; do not alter or stage the pre-existing local changes.
- Do not log, commit, or place real bootstrap, API, or administrator secrets in fixtures.
- Preserve legacy `X-Admin-Key` access for machine clients.
- Keep signed session expiry at 12 hours and use constant-time comparisons for session signatures, passwords, and CSRF values.
- Browser cookies must be `HttpOnly`, `SameSite=Lax`, and `Secure` whenever `DEBUG=false`.
- All authenticated, state-changing panel endpoints require a valid CSRF token; login is excluded because it is not yet an authenticated session.

---

## File Structure

- `app/config.py` — introduces the optional operator bootstrap secret setting.
- `app/admin/auth.py` — defines the typed signed-session payload and CSRF token derivation.
- `app/security.py` — resolves session principals through the database and verifies CSRF for protected browser mutations.
- `app/admin/router.py` — guards initial setup, emits secure cookies, provides template CSRF context, and attaches the CSRF dependency to authenticated POST routes.
- `app/admin/templates/base.html` — supplies a reusable hidden CSRF input macro.
- `app/admin/templates/{admins,appointments,availability,payments,professional_form,services,users}.html` — use the macro for each authenticated mutable form.
- `app/admin/templates/login.html` — adds the bootstrap-token field only while initial setup is enabled.
- `tests/test_admin_panel.py` — regression tests for bootstrap, session revocation, cookie attributes, and CSRF.

### Task 1: Define a signed session payload with a CSRF nonce

**Files:**
- Modify: `app/admin/auth.py`
- Modify: `tests/test_admin_panel.py`

**Interfaces:**
- Produces: `AdminSession(admin_user_id: int, expires_at: int, csrf_token: str)`.
- Produces: `issue_session(admin_user_id: int) -> str`, `read_session(cookie_value: str | None) -> AdminSession | None`, and `verify_csrf(session: AdminSession, supplied: str | None) -> bool`.

- [ ] **Step 1: Write failing unit tests for session payload behavior**

Add direct tests:

```python
def test_session_contains_a_nonempty_csrf_nonce():
    from app.admin import auth
    session = auth.read_session(auth.issue_session(42))
    assert session is not None
    assert session.admin_user_id == 42
    assert len(session.csrf_token) >= 32


def test_csrf_verification_rejects_a_different_nonce():
    from app.admin import auth
    session = auth.read_session(auth.issue_session(42))
    assert session is not None
    assert auth.verify_csrf(session, session.csrf_token)
    assert not auth.verify_csrf(session, "different-token")
```

- [ ] **Step 2: Run the tests and verify failure**

Run: `pytest tests/test_admin_panel.py -q`

Expected: failure because `read_session` currently returns an integer and no CSRF verifier exists.

- [ ] **Step 3: Implement the minimal signed payload extension**

Define the immutable payload type and return it after signature and expiry validation:

```python
from dataclasses import dataclass
import secrets


@dataclass(frozen=True)
class AdminSession:
    admin_user_id: int
    expires_at: int
    csrf_token: str


def issue_session(admin_user_id: int) -> str:
    payload = json.dumps({
        "sub": int(admin_user_id),
        "exp": int(time.time()) + _SESSION_TTL,
        "csrf": secrets.token_urlsafe(32),
    })
    # retain the existing signed-cookie encoding below this point


def verify_csrf(session: AdminSession, supplied: str | None) -> bool:
    return bool(supplied) and hmac.compare_digest(session.csrf_token, supplied)
```

Require `sub`, `exp`, and `csrf` to have valid types; return `None` for legacy or malformed cookie payloads rather than raising.

- [ ] **Step 4: Run session tests**

Run: `pytest tests/test_admin_panel.py -q`

Expected: session tests pass and existing panel tests are updated to access `session.admin_user_id` rather than comparing a raw integer.

- [ ] **Step 5: Commit session/CSRF primitives**

```bash
git add app/admin/auth.py tests/test_admin_panel.py
git commit -m "feat(admin): bind CSRF nonce to signed sessions"
```

### Task 2: Require a bootstrap secret and revalidate the administrator on each session request

**Files:**
- Modify: `app/config.py`
- Modify: `app/security.py`
- Modify: `app/admin/router.py`
- Modify: `app/admin/templates/login.html`
- Modify: `tests/test_admin_panel.py`

**Interfaces:**
- Consumes: `settings.admin_bootstrap_token` and `AdminSession.admin_user_id`.
- Produces: a first-run login that creates an administrator only when `bootstrap_token` compares equal to the configured operator secret; an inactive/deleted administrator session is rejected.

- [ ] **Step 1: Write failing authorization tests**

Add these tests, using `monkeypatch` to avoid real credentials:

```python
@pytest.fixture(autouse=True)
def _bootstrap_token(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "admin_bootstrap_token", "bootstrap-test-token")


def test_first_admin_requires_the_configured_bootstrap_token(anonymous_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "admin_bootstrap_token", "bootstrap-test-token")
    r = anonymous_client.post("/admin/login", data={"username": "admin", "password": "secret123"})
    assert r.status_code == 403


def test_disabled_admin_session_is_rejected(db_session, anonymous_client):
    login = _login(anonymous_client, bootstrap_token="bootstrap-test-token")
    cookie = login.headers["set-cookie"].split(";", 1)[0]
    admin = db_session.query(AdminUser).filter_by(username="admin").one()
    admin.is_active = False
    db_session.commit()
    assert anonymous_client.get("/admin", headers={"Cookie": cookie}).status_code == 401
```

Update `_login` so its default call includes `bootstrap_token="bootstrap-test-token"`; let a test pass an empty value when it must verify rejection.

- [ ] **Step 2: Run the tests and verify failure**

Run: `pytest tests/test_admin_panel.py -q`

Expected: first bootstrap still succeeds without a token and the disabled session still authorizes.

- [ ] **Step 3: Implement bootstrap and session-principal checks**

Add this setting:

```python
admin_bootstrap_token: str = ""
```

In `login_submit`, receive `bootstrap_token: str = Form("")`. On first run, reject with `HTTPException(status_code=403, detail="Initial administrator setup is disabled")` when the configured token is empty or does not satisfy:

```python
hmac.compare_digest(bootstrap_token, settings.admin_bootstrap_token)
```

In `require_admin`, inject `db: Session = Depends(get_db)`, load `AdminUser` by `session.admin_user_id`, and authorize only when that record exists and `is_active` is true. Keep the `X-Admin-Key` branch for machine clients. Update the first-run template to display a password input named `bootstrap_token`.

- [ ] **Step 4: Run the authorization tests**

Run: `pytest tests/test_admin_panel.py -q`

Expected: anonymous first-run setup without the token is rejected; a disabled administrator's signed cookie no longer authorizes.

- [ ] **Step 5: Commit bootstrap and revocation protection**

```bash
git add app/config.py app/security.py app/admin/router.py app/admin/templates/login.html tests/test_admin_panel.py
git commit -m "fix(admin): protect bootstrap and revoke disabled sessions"
```

### Task 3: Require CSRF for authenticated mutations and send secure production cookies

**Files:**
- Modify: `app/security.py`
- Modify: `app/admin/router.py`
- Modify: `app/admin/templates/base.html`
- Modify: `app/admin/templates/admins.html`
- Modify: `app/admin/templates/appointments.html`
- Modify: `app/admin/templates/availability.html`
- Modify: `app/admin/templates/payments.html`
- Modify: `app/admin/templates/professional_form.html`
- Modify: `app/admin/templates/services.html`
- Modify: `app/admin/templates/users.html`
- Modify: `tests/test_admin_panel.py`

**Interfaces:**
- Produces: `require_admin_csrf(request: Request) -> None` and template variable `csrf_token`.
- Consumes: hidden form field `_csrf` or header `X-CSRF-Token` and the signed `AdminSession` held in the session cookie.

- [ ] **Step 1: Write failing CSRF and cookie tests**

Add tests:

```python
def test_authenticated_mutation_requires_csrf(db_session, anonymous_client, monkeypatch):
    login = _login(anonymous_client, bootstrap_token="bootstrap-test-token")
    cookie = login.headers["set-cookie"].split(";", 1)[0]
    r = anonymous_client.post("/admin/logout", headers={"Cookie": cookie}, follow_redirects=False)
    assert r.status_code == 403


def test_login_cookie_is_secure_in_production(anonymous_client, monkeypatch):
    from app.admin import router
    monkeypatch.setattr(router.settings, "debug", False)
    r = _login(anonymous_client, bootstrap_token="bootstrap-test-token")
    assert "; Secure" in r.headers["set-cookie"]
```

Add a success case that extracts `csrf_token` from a rendered `/admin` page and sends it as `_csrf` to `/admin/logout`, expecting `303`.

- [ ] **Step 2: Run the tests and verify failure**

Run: `pytest tests/test_admin_panel.py -q`

Expected: logout succeeds without CSRF and the production cookie lacks `Secure`.

- [ ] **Step 3: Implement the dependency and template context**

Implement an async dependency that reads the signed session, accepts `X-CSRF-Token` or form `_csrf`, and returns `403` when `verify_csrf` is false:

```python
async def require_admin_csrf(request: Request) -> None:
    from app.admin import auth as admin_auth
    session = admin_auth.read_session(request.cookies.get(admin_auth.session_cookie_name()))
    form = await request.form()
    supplied = request.headers.get("X-CSRF-Token") or form.get("_csrf")
    if session is None or not admin_auth.verify_csrf(session, str(supplied or "")):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
```

Configure `Jinja2Templates` with a context processor that exposes `csrf_token` from the current valid session. Add this macro to `base.html`:

```jinja2
{% macro csrf_input() -%}
<input type="hidden" name="_csrf" value="{{ csrf_token }}">
{%- endmacro %}
```

Insert `{{ csrf_input() }}` inside every authenticated mutable form in the listed templates. Add `Depends(require_admin_csrf)` after `Depends(require_admin)` to every authenticated `@router.post` route, including logout. Set `secure=not settings.debug` in `_redirect_after_login`.

- [ ] **Step 4: Run panel tests and test the full suite**

Run:

```bash
pytest tests/test_admin_panel.py -q
pytest tests/ -q
```

Expected: missing or incorrect CSRF is rejected, valid CSRF succeeds, production cookies include `Secure`, and all tests pass.

- [ ] **Step 5: Commit CSRF and cookie hardening**

```bash
git add app/security.py app/admin/router.py app/admin/templates/base.html app/admin/templates/admins.html app/admin/templates/appointments.html app/admin/templates/availability.html app/admin/templates/payments.html app/admin/templates/professional_form.html app/admin/templates/services.html app/admin/templates/users.html tests/test_admin_panel.py
git commit -m "fix(admin): enforce CSRF and secure session cookies"
```

### Task 4: Complete the quality gate and deployment preparation

**Files:**
- Verify: all files changed by Tasks 1–3.

- [ ] **Step 1: Run static checks**

Run:

```bash
ruff check app/ tests/
mypy app/ --ignore-missing-imports
```

Expected: both commands exit `0`.

- [ ] **Step 2: Run migrations and tests against PostgreSQL**

Run:

```bash
DATABASE_URL=postgresql+psycopg://test:test@localhost:5432/test_db alembic upgrade head
DATABASE_URL=postgresql+psycopg://test:test@localhost:5432/test_db TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:5432/test_db API_KEY=test-api-key ADMIN_API_KEY=test-admin-key ASAAS_API_KEY=test ASAAS_WEBHOOK_TOKEN=test pytest tests/ -q
```

Expected: migration and test commands exit `0`.

- [ ] **Step 3: Inspect the review diff for accidental secrets and scope drift**

Run:

```bash
git diff origin/master...HEAD --check
git diff --name-only origin/master...HEAD
git grep -n -E '(API_KEY|ADMIN_BOOTSTRAP_TOKEN)=.{16,}' -- ':!*.example' ':!docs/superpowers/plans/*'
```

Expected: no whitespace errors, only planned admin-auth files change, and no credential assignment is tracked.

- [ ] **Step 4: Publish for review after verification**

```bash
git push -u origin codex/admin-security-hardening
gh pr create --base master --head codex/admin-security-hardening --title "Harden administrator authentication" --fill
```

Expected: the pull request is limited to panel authentication hardening and can be deployed independently from the MCP network changes.
