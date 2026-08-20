from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.admin.schemas import AppointmentAction, PaymentAction
from app.admin.service import AdminService
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory="app/admin/templates")


async def verify_admin_key(x_admin_key: str = Header(...)):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Admin access denied")


@router.get("", response_class=HTMLResponse, dependencies=[Depends(verify_admin_key)])
async def dashboard(request: Request, db: Session = Depends(get_db)):
    service = AdminService(db)
    kpis = service.get_kpis()
    professionals = service.list_professionals()[:5]  # Top 5 para o dashboard

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "kpis": kpis,
        "professionals": professionals,
    })


@router.get("/appointments", response_class=HTMLResponse, dependencies=[Depends(verify_admin_key)])
async def appointments_page(
    request: Request,
    date_from: date | None = None,
    date_to: date | None = None,
    professional_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    service = AdminService(db)
    appointments, total = service.list_appointments(
        date_from=date_from,
        date_to=date_to,
        professional_id=professional_id,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    professionals = service.list_professionals()

    total_pages = (total + page_size - 1) // page_size

    return templates.TemplateResponse("appointments.html", {
        "request": request,
        "appointments": appointments,
        "professionals": professionals,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "filters": {
            "date_from": date_from,
            "date_to": date_to,
            "professional_id": professional_id,
            "status": status,
            "search": search,
        },
    })


@router.get("/appointments/{appointment_id}", response_class=HTMLResponse, dependencies=[Depends(verify_admin_key)])
async def appointment_detail(
    request: Request,
    appointment_id: int,
    db: Session = Depends(get_db),
):
    service = AdminService(db)
    detail = service.get_appointment_detail(appointment_id)

    if not detail:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    return templates.TemplateResponse("appointment_detail.html", {
        "request": request,
        "detail": detail,
    })


@router.post("/appointments/{appointment_id}/action", dependencies=[Depends(verify_admin_key)])
async def appointment_action(
    appointment_id: int,
    action: AppointmentAction,
    db: Session = Depends(get_db),
):
    service = AdminService(db)
    result = service.appointment_action(appointment_id, action.action, action.notes)

    if result is None:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/payments", response_class=HTMLResponse, dependencies=[Depends(verify_admin_key)])
async def payments_page(
    request: Request,
    date_from: date | None = None,
    date_to: date | None = None,
    professional_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    service = AdminService(db)
    payments, total = service.list_payments(
        date_from=date_from,
        date_to=date_to,
        professional_id=professional_id,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    professionals = service.list_professionals()

    total_pages = (total + page_size - 1) // page_size

    return templates.TemplateResponse("payments.html", {
        "request": request,
        "payments": payments,
        "professionals": professionals,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "filters": {
            "date_from": date_from,
            "date_to": date_to,
            "professional_id": professional_id,
            "status": status,
            "search": search,
        },
    })


@router.post("/payments/{payment_id}/action", dependencies=[Depends(verify_admin_key)])
async def payment_action(
    payment_id: int,
    action: PaymentAction,
    db: Session = Depends(get_db),
):
    service = AdminService(db)
    result = service.payment_action(payment_id, action.action)

    if result is None:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/professionals", response_class=HTMLResponse, dependencies=[Depends(verify_admin_key)])
async def professionals_page(request: Request, db: Session = Depends(get_db)):
    service = AdminService(db)
    professionals = service.list_professionals()

    return templates.TemplateResponse("professionals.html", {
        "request": request,
        "professionals": professionals,
    })


# --- API Endpoints para HTMX partials ---

@router.get("/api/kpis", dependencies=[Depends(verify_admin_key)])
async def api_kpis(db: Session = Depends(get_db)):
    service = AdminService(db)
    return service.get_kpis()


@router.get("/api/appointments", dependencies=[Depends(verify_admin_key)])
async def api_appointments(
    date_from: date | None = None,
    date_to: date | None = None,
    professional_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    service = AdminService(db)
    appointments, total = service.list_appointments(
        date_from=date_from,
        date_to=date_to,
        professional_id=professional_id,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size
    return {
        "data": appointments,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/api/payments", dependencies=[Depends(verify_admin_key)])
async def api_payments(
    date_from: date | None = None,
    date_to: date | None = None,
    professional_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    service = AdminService(db)
    payments, total = service.list_payments(
        date_from=date_from,
        date_to=date_to,
        professional_id=professional_id,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    total_pages = (total + page_size - 1) // page_size
    return {
        "data": payments,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/api/professionals", dependencies=[Depends(verify_admin_key)])
async def api_professionals(db: Session = Depends(get_db)):
    service = AdminService(db)
    return service.list_professionals()