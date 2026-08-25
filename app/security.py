import base64
import binascii
import hashlib
import hmac
import logging
from typing import Annotated

from fastapi import Header, HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)


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


def require_admin(
    request: Request,
    x_admin_key: Annotated[str | None, Header()] = None,
) -> None:
    if x_admin_key is not None:
        if hmac.compare_digest(x_admin_key, settings.admin_api_key):
            return
        raise HTTPException(status_code=403, detail="Admin access denied")

    username, password = _decode_basic_credentials(request)
    if username and hmac.compare_digest(password, settings.admin_api_key):
        return
    raise HTTPException(
        status_code=401,
        detail="Admin authentication required",
        headers={"WWW-Authenticate": 'Basic realm="Agenda Atende Admin"'},
    )
