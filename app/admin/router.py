from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.admin.schemas import (
    AdminAppointmentCreate,
    AdminAppointmentUpdate,
    AppointmentAction,
    PaymentAction,
)
from app.admin.service import AdminService
from app.database import get_db
from app.models.payment import Payment
from app.models.service import Service
from app.models.user import User
from app.security import require_admin
from app.services.asaas_client import AsaasIntegrationError
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory="app/admin/templates")


@router.get("", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def dashboard(request: Request, db: Session = Depends(get_db)):
    service = AdminService(db)
    kpis = service.get_kpis()
    professionals = service.list_professionals()[:5]  # Top 5 para o dashboard

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "kpis": kpis,
        "professionals": professionals,
    })


@router.get("/appointments", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def appointments_page(
    request: Request,
    date_from: date | None = None,
    date_to: date | None = None,
    professional_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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
    appointment_options = {
        "professionals": [
            {"id": professional["id"], "name": professional["name"]}
            for professional in professionals
            if professional["active"]
        ],
        "services": [
            {"id": service.id, "name": service.name}
            for service in db.query(Service)
            .filter(Service.active.is_(True))
            .order_by(Service.name)
            .all()
        ],
        "clients": [
            {"id": client.id, "name": client.name, "phone": client.phone}
            for client in db.query(User).order_by(User.name).all()
        ],
    }

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
        "appointment_options": appointment_options,
    })


@router.get("/appointments/{appointment_id}", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
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


@router.post("/appointments/{appointment_id}/action", dependencies=[Depends(require_admin)])
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


@router.get("/payments", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def payments_page(
    request: Request,
    date_from: date | None = None,
    date_to: date | None = None,
    professional_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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


@router.post("/payments/{payment_id}/action", dependencies=[Depends(require_admin)])
async def payment_action(
    payment_id: int,
    action: PaymentAction,
    db: Session = Depends(get_db),
):
    if not db.query(Payment.id).filter(Payment.id == payment_id).first():
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    service = PaymentService(db)
    try:
        if action.action == "refresh":
            payment = await service.refresh(payment_id)
        else:
            payment = await service.refund(payment_id)
    except AsaasIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"id": payment.id, "status": payment.status}


@router.get("/professionals", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def professionals_page(request: Request, db: Session = Depends(get_db)):
    service = AdminService(db)
    professionals = service.list_professionals()

    return templates.TemplateResponse("professionals.html", {
        "request": request,
        "professionals": professionals,
    })


# --- API Endpoints para HTMX partials ---

@router.post(
    "/api/appointments",
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_admin_appointment(
    data: AdminAppointmentCreate, db: Session = Depends(get_db)
):
    try:
        return AdminService(db).create_appointment(data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/api/appointments/{appointment_id}", dependencies=[Depends(require_admin)])
async def update_admin_appointment(
    appointment_id: int,
    data: AdminAppointmentUpdate,
    db: Session = Depends(get_db),
):
    try:
        appointment = AdminService(db).update_appointment(appointment_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not appointment:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    return appointment


@router.delete(
    "/api/appointments/{appointment_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
async def delete_admin_appointment(
    appointment_id: int, db: Session = Depends(get_db)
):
    try:
        deleted = AdminService(db).delete_appointment(appointment_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")


@router.get("/api/kpis", dependencies=[Depends(require_admin)])
async def api_kpis(db: Session = Depends(get_db)):
    service = AdminService(db)
    return service.get_kpis()


@router.get("/api/appointments", dependencies=[Depends(require_admin)])
async def api_appointments(
    date_from: date | None = None,
    date_to: date | None = None,
    professional_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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


@router.get("/api/payments", dependencies=[Depends(require_admin)])
async def api_payments(
    date_from: date | None = None,
    date_to: date | None = None,
    professional_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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


@router.get("/api/professionals", dependencies=[Depends(require_admin)])
async def api_professionals(
    limit: int | None = Query(None, ge=1, le=5),
    db: Session = Depends(get_db),
):
    service = AdminService(db)
    professionals = service.list_professionals()
    return professionals[:limit] if limit is not None else professionals
