import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Response
from fastapi.responses import RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from app.admin.router import router as admin_router
from app.api.appointments import router as appointments_router
from app.api.availability import router as availability_router
from app.api.health import router as health_router
from app.api.payments import router as payments_router
from app.api.professionals import router as professionals_router
from app.api.services import router as services_router
from app.api.users import router as users_router
from app.api.webhooks import router as webhooks_router
from app.config import Settings, settings
from app.database import SessionLocal
from app.mcp.router import router as mcp_router
from app.repositories.appointment_repo import AppointmentRepository
from app.security import require_api_key

logger = logging.getLogger(__name__)


async def _expiration_worker():
    """Background task to reliably expire pending reservations every 5 minutes."""
    while True:
        try:
            await asyncio.sleep(300)
            with SessionLocal() as db:
                repo = AppointmentRepository(db)
                expired = repo.expire_reservations(datetime.now(UTC))
                if expired > 0:
                    db.commit()
                    logger.info("Automatically expired %d pending reservation(s)", expired)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error in reservation expiration worker")


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(_expiration_worker())
    yield
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


def create_app(app_settings: Settings = settings) -> FastAPI:
    docs_url = "/docs" if app_settings.debug else None
    redoc_url = "/redoc" if app_settings.debug else None
    openapi_url = "/openapi.json" if app_settings.debug else None
    application = FastAPI(
        title=app_settings.app_name,
        debug=app_settings.debug,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    application.include_router(health_router)
    application.include_router(users_router)
    application.include_router(professionals_router)
    application.include_router(services_router)
    application.include_router(availability_router)
    application.include_router(appointments_router)
    application.include_router(payments_router)
    application.include_router(webhooks_router)
    application.include_router(mcp_router)
    application.include_router(admin_router)

    Instrumentator().instrument(application)

    @application.get(
        "/metrics",
        include_in_schema=False,
        dependencies=[Depends(require_api_key)],
    )
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return application


app = create_app()
