from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request as FastAPIRequest
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.mcp.tools import TOOL_DEFINITIONS, handle_tool_call

router = APIRouter(prefix="/mcp", tags=["mcp"])


def verify_auth(request: FastAPIRequest):
    auth = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.api_key}"
    if auth != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("")
async def mcp_endpoint(request: FastAPIRequest, db: Session = Depends(get_db)):
    verify_auth(request)

    body = await request.json()
    method = body.get("method", "")
    req_id = body.get("id", None)
    params = body.get("params", {}) or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agenda_atende", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOL_DEFINITIONS},
        }

    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = await handle_tool_call(name, arguments, db)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Método não encontrado: {method}"},
    }
