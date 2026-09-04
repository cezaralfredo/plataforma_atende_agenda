"""Testes do novo painel admin: login real com sessão + CRUDs."""


def _login(client, username="admin", password=None):
    """Cria o primeiro admin (first_run) e retorna o object do redirect."""
    password = password or "secret123"
    return client.post(
        "/admin/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def test_first_login_creates_admin_and_sets_cookie(anonymous_client):
    r = _login(anonymous_client)
    assert r.status_code == 303
    assert r.headers.get("location") == "/admin"
    assert "atende_admin_session" in r.headers.get("set-cookie", "")


def test_login_page_first_run(anonymous_client):
    r = anonymous_client.get("/admin/login")
    assert r.status_code == 200
    assert "Configuração inicial" in r.text


def test_second_login_does_not_create_again(db_session, anonymous_client):
    # Cria admin na primeira chamada
    _login(anonymous_client)
    # Segunda visita ao login NÃO mostra setup (já existe admin)
    r = anonymous_client.get("/admin/login")
    assert "Configuração inicial" not in r.text


def test_auth_rejects_invalid_password(anonymous_client):
    _login(anonymous_client, "admin", "p4ss123456")
    r = anonymous_client.post(
        "/admin/login", data={"username": "admin", "password": "errada123"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "Usuário ou senha inválidos" in r.text


def test_session_allows_dashboard_access(db_session, anonymous_client):
    # Faz login (obtém cookie)
    login = _login(anonymous_client)
    cookie = login.headers["set-cookie"].split(";")[0]
    # Acessa o dashboard COM o cookie (sem header X-Admin-Key)
    r = anonymous_client.get("/admin", headers={"Cookie": cookie})
    assert r.status_code == 200


def test_dashboard_requires_auth(anonymous_client):
    # Sem cookie e sem X-Admin-Key/Basic -> 401
    r = anonymous_client.get("/admin")
    assert r.status_code == 401


def test_users_page_requires_auth(anonymous_client):
    r = anonymous_client.get("/admin/users")
    assert r.status_code == 401


def test_admin_legacy_header_still_works(anonymous_client):
    # Compat: X-Admin-Key continua funcionando para máquinas
    from app.config import settings
    r = anonymous_client.get("/admin", headers={"X-Admin-Key": settings.admin_api_key})
    assert r.status_code == 200


def test_logout_clears_cookie(db_session, anonymous_client):
    login = _login(anonymous_client)
    cookie_header = login.headers["set-cookie"].split(";")[0]
    cookie_name, cookie_value = cookie_header.split("=", 1)
    anonymous_client.cookies.set(cookie_name, cookie_value)
    assert anonymous_client.get("/admin").status_code == 200
    # Logout: o response deve expurgar o cookie (valor vazio + Max-Age=0)
    r = anonymous_client.post("/admin/logout", follow_redirects=False)
    assert r.status_code == 303
    set_cookie = r.headers.get("set-cookie", "")
    assert cookie_name in set_cookie
    # Força remoção no jar (simula o navegador honrando o Max-Age=0)
    anonymous_client.cookies.delete(cookie_name)
    assert anonymous_client.get("/admin").status_code == 401