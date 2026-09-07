import base64
import binascii
import hashlib
import hmac
import logging
from typing import Annotated

from fastapi import Header, HTTPException, Request

from app.config import settings

# The production container exposes Uvicorn's error channel.  Use the same
# logger so rejection diagnostics are visible in the operational log stream.
logger = logging.getLogger("uvicorn.error")


def require_api_key(request: Request) -> None:
    supplied = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.api_key}"
    if not hmac.compare_digest(supplied, expected):
        reason = "missing" if not supplied else "invalid"
        # This digest supports correlation of repeated invalid credentials
        # without writing the credential itself to logs.
        credential_id = "-" if not supplied else hashlib.sha256(supplied.encode()).hexdigest()[:12]
        logger.warning(
            "API authorization rejected path=%s reason=%s credential_id=%s client=%s user_agent=%s",
            request.url.path,
            reason,
            credential_id,
            request.client.host if request.client else "unknown",
            request.headers.get("user-agent", "unknown"),
        )
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _decode_basic_credentials(request: Request) -> tuple[str, str]:
    authorization = request.headers.get("Authorization", "")
    scheme, _, encoded = authorization.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return "", ""
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return "", ""
    username, separator, password = decoded.partition(":")
    if not separator:
        return "", ""
    return username, password


def _is_browser_request(request: Request) -> bool:
    """Navegadores enviam Accept contendo text/html; requests de maquina (API/MCP)
    na maioria das vezes enviam application/json ou Accept vazio ou */*."""
    accept = request.headers.get("accept", "")
    return "text/html" in accept


def require_admin(
    request: Request,
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    # 1) Sessão de navegador (cookie assinado) — login real do painel.
    try:
        from app.admin import auth as admin_auth
        if admin_auth.read_session(request.cookies.get(admin_auth.session_cookie_name())) is not None:
            return
    except Exception:
        logger.debug("Admin session cookie ignored (invalid)", exc_info=True)

    # 2) X-Admin-Key header (máquinas / MCP / scripts)
    if x_admin_key is not None:
        if hmac.compare_digest(x_admin_key, settings.admin_api_key):
            return
        raise HTTPException(status_code=403, detail="Admin access denied")

    # 3) Basic Auth (legacy)
    username, password = _decode_basic_credentials(request)
    if username and hmac.compare_digest(password, settings.admin_api_key):
        return

    # 4) Navegador sem sessão -> redirecionar para a tela de login.
    #    IMPORTANTE: rotas usam dependencies=[Depends(require_admin)]; o FastAPI
    #    IGNORA o retorno da dependência, só exceções propagam. Por isso
    #    redirecionamos via HTTPException(302)+Location, que o browser segue.
    if _is_browser_request(request):
        raise HTTPException(
            status_code=302,
            detail="Redirect to login",
            headers={"Location": "/admin/login"},
        )

    # 5) Máquina não autorizada -> 401 (desafio Basic, sem redirecionamento).
    raise HTTPException(
        status_code=401,
        detail="Admin authentication required",
        headers={"WWW-Authenticate": 'Basic realm="Agenda Atende Admin"'},
    )
