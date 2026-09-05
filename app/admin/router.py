from datetime import date
from datetime import time as dtime

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.admin import auth as admin_auth
from app.admin.schemas import AppointmentAction, PaymentAction
from app.admin.service import AdminService, AdminUserService
from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.payment import Payment
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
async def api_professionals(db: Session = Depends(get_db)):
    service = AdminService(db)
    return service.list_professionals()


# ===========================================================================
# Autenticação — Login real (sessão) e usuários administradores
# ===========================================================================
def _redirect_after_login(request: Request, admin: AdminUser) -> RedirectResponse:
    resp = RedirectResponse(url="/admin", status_code=303)
    resp.set_cookie(
        key=admin_auth.session_cookie_name(),
        value=admin_auth.issue_session(admin.id),
        max_age=admin_auth.session_ttl(),
        httponly=True,
        samesite="lax",
    )
    return resp


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    """Tela de login. Se ainda não houver admin cadastrado, vira setup inicial."""
    svc = AdminUserService(db)
    first_run = svc.count() == 0
    return templates.TemplateResponse("login.html", {
        "request": request,
        "first_run": first_run,
        "error": None,
    })


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    svc = AdminUserService(db)
    first_run = svc.count() == 0

    # Primeiro acesso: cria o administrador inicial.
    if first_run:
        if len(username.strip()) < 3 or len(password) < 6:
            return templates.TemplateResponse("login.html", {
                "request": request, "first_run": True,
                "error": "Informe um usuário (mín. 3) e senha (mín. 6) para criar o administrador.",
                "prefill_username": username,
            })
        try:
            admin = svc.create(username=username, password=password,
                               display_name=username.strip() or "Administrador")
        except ValueError as exc:
            return templates.TemplateResponse("login.html", {
                "request": request, "first_run": True, "error": str(exc), "prefill_username": username,
            })
        return _redirect_after_login(request, admin)

    authed = svc.authenticate(username, password)
    if not authed:
        return templates.TemplateResponse("login.html", {
            "request": request, "first_run": False,
            "error": "Usuário ou senha inválidos.", "prefill_username": username,
        })
    return _redirect_after_login(request, authed)


@router.post("/logout")
async def logout():
    resp = RedirectResponse(url="/admin/login", status_code=303)
    resp.delete_cookie(admin_auth.session_cookie_name())
    return resp


# --- Gerenciar usuários administradores (requer sessão ou key) ---
@router.get("/admins", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_users_page(request: Request, db: Session = Depends(get_db)):
    svc = AdminUserService(db)
    return templates.TemplateResponse("admins.html", {"request": request, "admins": svc.list_admins()})


@router.post("/admins", dependencies=[Depends(require_admin)])
async def admin_users_create(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    display_name: str = Form(""),
    db: Session = Depends(get_db),
):
    svc = AdminUserService(db)
    try:
        svc.create(username=username, password=password, display_name=display_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RedirectResponse(url="/admin/admins", status_code=303)


@router.post("/admins/{admin_id}/toggle", dependencies=[Depends(require_admin)])
async def admin_users_toggle(admin_id: int, db: Session = Depends(get_db)):
    svc = AdminUserService(db)
    admin = svc.get(admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin não encontrado")
    if svc.count() <= 1 and admin.is_active:
        raise HTTPException(status_code=400, detail="Não é possível desativar o único administrador.")
    svc.set_active(admin, not admin.is_active)
    return RedirectResponse(url="/admin/admins", status_code=303)


@router.post("/admins/{admin_id}/delete", dependencies=[Depends(require_admin)])
async def admin_users_delete(admin_id: int, db: Session = Depends(get_db)):
    svc = AdminUserService(db)
    admin = svc.get(admin_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin não encontrado")
    if svc.count() <= 1:
        raise HTTPException(status_code=400, detail="Não é possível remover o único administrador.")
    svc.delete(admin)
    return RedirectResponse(url="/admin/admins", status_code=303)


# ===========================================================================
# CRUD — Clientes (User)
# ===========================================================================
@router.get("/users", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def users_page(
    request: Request,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    svc = AdminService(db)
    users, total = svc.list_users(search=search, page=page, page_size=page_size)
    return templates.TemplateResponse("users.html", {
        "request": request, "users": users, "total": total, "page": page,
        "page_size": page_size, "search": search,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    })


@router.post("/users", dependencies=[Depends(require_admin)])
async def users_create(
    request: Request,
    name: str = Form(""), phone: str = Form(""), email: str = Form(""),
    whatsapp_number: str = Form(""), cpf_cnpj: str = Form(""),
    db: Session = Depends(get_db),
):
    svc = AdminService(db)
    try:
        svc.create_user(name=name, phone=phone, email=email or None,
                        whatsapp_number=whatsapp_number or None, cpf_cnpj=cpf_cnpj or None)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erro ao cadastrar cliente: {exc}")
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/update", dependencies=[Depends(require_admin)])
async def users_update(
    user_id: int,
    name: str = Form(""), phone: str = Form(""), email: str = Form(""),
    whatsapp_number: str = Form(""), cpf_cnpj: str = Form(""),
    db: Session = Depends(get_db),
):
    svc = AdminService(db)
    user = svc.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    svc.update_user(user, name=name, phone=phone, email=email or None,
                    whatsapp_number=whatsapp_number or None, cpf_cnpj=cpf_cnpj or None)
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/users/{user_id}/delete", dependencies=[Depends(require_admin)])
async def users_delete(user_id: int, db: Session = Depends(get_db)):
    svc = AdminService(db)
    user = svc.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    svc.delete_user(user)
    return RedirectResponse(url="/admin/users", status_code=303)


# ===========================================================================
# CRUD — Profissionais (Professional)
# ===========================================================================
@router.get("/professionals/create", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def professional_create_page(request: Request):
    return templates.TemplateResponse("professional_form.html", {"request": request, "professional": None})


@router.post("/professionals", dependencies=[Depends(require_admin)])
async def professionals_create(
    request: Request,
    name: str = Form(""), phone: str = Form(""), email: str = Form(""),
    bio: str = Form(""), active: str = Form("1"),
    db: Session = Depends(get_db),
):
    svc = AdminService(db)
    svc.create_professional(name=name, phone=phone or None, email=email or None,
                           bio=bio or None, active=(active == "1"))
    return RedirectResponse(url="/admin/professionals", status_code=303)


@router.get("/professionals/{professional_id}/edit", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def professional_edit_page(professional_id: int, request: Request, db: Session = Depends(get_db)):
    svc = AdminService(db)
    prof = svc.get_professional(professional_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    return templates.TemplateResponse("professional_form.html", {"request": request, "professional": prof})


@router.post("/professionals/{professional_id}/update", dependencies=[Depends(require_admin)])
async def professionals_update(
    professional_id: int,
    name: str = Form(""), phone: str = Form(""), email: str = Form(""),
    bio: str = Form(""), active: str = Form("1"),
    db: Session = Depends(get_db),
):
    svc = AdminService(db)
    prof = svc.get_professional(professional_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    svc.update_professional(prof, name=name, phone=phone or None, email=email or None,
                            bio=bio or None, active=(active == "1"))
    return RedirectResponse(url="/admin/professionals", status_code=303)


@router.post("/professionals/{professional_id}/delete", dependencies=[Depends(require_admin)])
async def professionals_delete(professional_id: int, db: Session = Depends(get_db)):
    svc = AdminService(db)
    prof = svc.get_professional(professional_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    svc.delete_professional(prof)
    return RedirectResponse(url="/admin/professionals", status_code=303)


# ===========================================================================
# CRUD — Serviços (Service) e valores
# ===========================================================================
@router.get("/services", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def services_page(request: Request, professional_id: int | None = None, db: Session = Depends(get_db)):
    svc = AdminService(db)
    services = svc.list_services_raw(professional_id)
    professionals = svc.list_professionals_raw()
    return templates.TemplateResponse("services.html", {
        "request": request, "services": services, "professionals": professionals,
        "filter_professional": professional_id,
    })


@router.post("/services", dependencies=[Depends(require_admin)])
async def services_create(
    request: Request,
    professional_id: int = Form(...), name: str = Form(""),
    duration_minutes: int = Form(30), price: str = Form("0.00"),
    description: str = Form(""), category: str = Form(""),
    db: Session = Depends(get_db),
):
    svc = AdminService(db)
    price_cents = round(float(price or 0) * 100)
    svc.create_service(professional_id=professional_id, name=name, duration_minutes=duration_minutes,
                       price_cents=price_cents, description=description or None, category=category or None)
    return RedirectResponse(url="/admin/services", status_code=303)


@router.post("/services/{service_id}/update", dependencies=[Depends(require_admin)])
async def services_update(
    service_id: int,
    professional_id: int = Form(...), name: str = Form(""),
    duration_minutes: int = Form(30), price: str = Form("0.00"),
    description: str = Form(""), category: str = Form(""),
    db: Session = Depends(get_db),
):
    svc = AdminService(db)
    s = svc.get_service(service_id)
    if not s:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    price_cents = round(float(price or 0) * 100)
    svc.update_service(s, professional_id=professional_id, name=name, duration_minutes=duration_minutes,
                       price_cents=price_cents, description=description or None, category=category or None)
    return RedirectResponse(url="/admin/services", status_code=303)


@router.post("/services/{service_id}/delete", dependencies=[Depends(require_admin)])
async def services_delete(service_id: int, db: Session = Depends(get_db)):
    svc = AdminService(db)
    s = svc.get_service(service_id)
    if not s:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    svc.delete_service(s)
    return RedirectResponse(url="/admin/services", status_code=303)


# ===========================================================================
# CRUD — Horários / Disponibilidade (Availability)
# ===========================================================================
@router.get("/availability", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def availability_page(request: Request, professional_id: int | None = None, db: Session = Depends(get_db)):
    svc = AdminService(db)
    slots = svc.list_availability_raw(professional_id)
    professionals = svc.list_professionals_raw()
    return templates.TemplateResponse("availability.html", {
        "request": request, "slots": slots, "professionals": professionals,
        "filter_professional": professional_id,
        "weekday_names": ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"],
    })


@router.post("/availability", dependencies=[Depends(require_admin)])
async def availability_create(
    request: Request,
    professional_id: int = Form(...), start_time: str = Form(...), end_time: str = Form(...),
    day_of_week: int | None = Form(None), specific_date: str = Form(""),
    db: Session = Depends(get_db),
):
    svc = AdminService(db)
    sh, sm = map(int, start_time.split(":")[:2])
    eh, em = map(int, end_time.split(":")[:2])
    st = dtime(sh, sm)
    et = dtime(eh, em)
    sdate = date.fromisoformat(specific_date) if specific_date else None
    svc.create_availability(professional_id=professional_id, start_time=st, end_time=et,
                            day_of_week=day_of_week, specific_date=sdate)
    return RedirectResponse(url="/admin/availability", status_code=303)


@router.post("/availability/{slot_id}/delete", dependencies=[Depends(require_admin)])
async def availability_delete(slot_id: int, db: Session = Depends(get_db)):
    svc = AdminService(db)
    a = svc.get_availability(slot_id)
    if not a:
        raise HTTPException(status_code=404, detail="Horário não encontrado")
    svc.delete_availability(a)
    return RedirectResponse(url="/admin/availability", status_code=303)
