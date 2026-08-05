from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.health import router as health_router
from app.api.users import router as users_router
from app.api.professionals import router as professionals_router
from app.api.services import router as services_router
from app.api.availability import router as availability_router
from app.api.appointments import router as appointments_router
from app.api.webhooks import router as webhooks_router
from app.api.payments import router as payments_router
from app.mcp.router import router as mcp_router
from app.admin.router import router as admin_router
from app.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.include_router(health_router)
app.include_router(users_router)
app.include_router(professionals_router)
app.include_router(services_router)
app.include_router(availability_router)
app.include_router(appointments_router)
app.include_router(payments_router)
app.include_router(webhooks_router)
app.include_router(mcp_router)
app.include_router(admin_router)

# Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
