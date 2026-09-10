from datetime import date, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.availability import Availability
from app.models.payment import Payment
from app.models.professional import Professional
from app.models.professional_service import ProfessionalService
from app.models.service import Service
from app.models.user import User
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.schemas.user import UserCreate
from app.services.appointment_service import AppointmentService
from app.services.professional_service import ProfessionalManagementService
from app.services.professional_service_offering_service import ProfessionalOfferingService
from app.services.service_service import ServiceCatalogService
from app.services.user_service import UserService


class AdminService:
    def __init__(self, db: Session):
        self.db = db

    def get_kpis(self) -> dict:
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Appointments today
        appointments_today = self.db.query(func.count(Appointment.id)).filter(
            func.date(Appointment.start_time) == today
        ).scalar() or 0

        # Appointments by status
        appointments_pending = self.db.query(func.count(Appointment.id)).filter(
            Appointment.status == "pending"
        ).scalar() or 0

        appointments_confirmed = self.db.query(func.count(Appointment.id)).filter(
            Appointment.status == "confirmed"
        ).scalar() or 0

        # Revenue (confirmed + completed appointments with payments received)
        revenue_today = self.db.query(func.coalesce(func.sum(Payment.amount_cents), 0)).join(
            Appointment, Payment.appointment_id == Appointment.id
        ).filter(
            and_(
                func.date(Appointment.start_time) == today,
                Payment.status.in_(["received", "confirmed"])
            )
        ).scalar() or 0

        revenue_week = self.db.query(func.coalesce(func.sum(Payment.amount_cents), 0)).join(
            Appointment, Payment.appointment_id == Appointment.id
        ).filter(
            and_(
                func.date(Appointment.start_time) >= week_ago,
                Payment.status.in_(["received", "confirmed"])
            )
        ).scalar() or 0

        revenue_month = self.db.query(func.coalesce(func.sum(Payment.amount_cents), 0)).join(
            Appointment, Payment.appointment_id == Appointment.id
        ).filter(
            and_(
                func.date(Appointment.start_time) >= month_ago,
                Payment.status.in_(["received", "confirmed"])
            )
        ).scalar() or 0

        # Payments pending/overdue
        payments_pending = self.db.query(func.count(Payment.id)).filter(
            Payment.status == "pending"
        ).scalar() or 0

        payments_overdue = self.db.query(func.count(Payment.id)).filter(
            Payment.status == "overdue"
        ).scalar() or 0

        # Professionals
        professionals_active = self.db.query(func.count(Professional.id)).filter(
            Professional.active.is_(True)
        ).scalar() or 0

        professionals_total = self.db.query(func.count(Professional.id)).scalar() or 0

        # Users
        users_total = self.db.query(func.count(User.id)).scalar() or 0

        return {
            "appointments_today": appointments_today,
            "appointments_pending": appointments_pending,
            "appointments_confirmed": appointments_confirmed,
            "revenue_today_cents": int(revenue_today),
            "revenue_week_cents": int(revenue_week),
            "revenue_month_cents": int(revenue_month),
            "payments_pending": payments_pending,
            "payments_overdue": payments_overdue,
            "professionals_active": professionals_active,
            "professionals_total": professionals_total,
            "users_total": users_total,
        }

    def list_appointments(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        professional_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        latest_payment_id = (
            select(func.max(Payment.id))
            .where(Payment.appointment_id == Appointment.id)
            .correlate(Appointment)
            .scalar_subquery()
        )
        query = self.db.query(
            Appointment,
            User.name.label("client_name"),
            User.phone.label("client_phone"),
            Professional.name.label("professional_name"),
            Service.name.label("service_name"),
            Service.price_cents.label("service_price_cents"),
            Payment.status.label("payment_status"),
            Payment.id.label("payment_id"),
        ).outerjoin(User, Appointment.user_id == User.id).outerjoin(
            Professional, Appointment.professional_id == Professional.id
        ).outerjoin(Service, Appointment.service_id == Service.id).outerjoin(
            Payment, Payment.id == latest_payment_id
        )

        if date_from:
            query = query.filter(func.date(Appointment.start_time) >= date_from)
        if date_to:
            query = query.filter(func.date(Appointment.start_time) <= date_to)
        if professional_id:
            query = query.filter(Appointment.professional_id == professional_id)
        if status:
            query = query.filter(Appointment.status == status)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.name.ilike(search_term),
                    User.phone.ilike(search_term),
                    Professional.name.ilike(search_term),
                    Service.name.ilike(search_term),
                )
            )

        total = query.count()

        query = query.order_by(Appointment.start_time.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        results = query.all()

        appointments = []
        for row in results:
            apt, client_name, client_phone, prof_name, svc_name, svc_price, pay_status, pay_id = row
            appointments.append({
                "id": apt.id,
                "user_id": apt.user_id,
                "professional_id": apt.professional_id,
                "service_id": apt.service_id,
                "start_time": apt.start_time,
                "end_time": apt.end_time,
                "status": apt.status,
                "expires_at": apt.expires_at,
                "notes": apt.notes,
                "created_at": apt.created_at,
                "client_name": client_name,
                "client_phone": client_phone,
                "professional_name": prof_name,
                "service_name": svc_name,
                "service_price_cents": (
                    apt.service_price_cents
                    if apt.service_price_cents is not None
                    else svc_price
                ),
                "payment_status": pay_status,
                "payment_id": pay_id,
            })

        return appointments, total

    def list_payments(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
        professional_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
        archived: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        query = self.db.query(
            Payment,
            User.name.label("client_name"),
            User.phone.label("client_phone"),
            Professional.name.label("professional_name"),
            Service.name.label("service_name"),
            Appointment.start_time.label("appointment_start"),
        ).join(Appointment, Payment.appointment_id == Appointment.id).outerjoin(
            User, Appointment.user_id == User.id
        ).outerjoin(Professional, Appointment.professional_id == Professional.id).outerjoin(
            Service, Appointment.service_id == Service.id
        )

        if archived:
            query = query.filter(Payment.archived_at.isnot(None))
        else:
            query = query.filter(Payment.archived_at.is_(None))

        if date_from:
            query = query.filter(func.date(Appointment.start_time) >= date_from)
        if date_to:
            query = query.filter(func.date(Appointment.start_time) <= date_to)
        if professional_id:
            query = query.filter(Appointment.professional_id == professional_id)
        if status:
            query = query.filter(Payment.status == status)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    User.name.ilike(search_term),
                    User.phone.ilike(search_term),
                    Professional.name.ilike(search_term),
                    Payment.asaas_payment_id.ilike(search_term),
                )
            )

        total = query.count()

        query = query.order_by(Payment.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        results = query.all()

        payments = []
        for row in results:
            pay, client_name, client_phone, prof_name, svc_name, apt_start = row
            payments.append({
                "id": pay.id,
                "appointment_id": pay.appointment_id,
                "asaas_payment_id": pay.asaas_payment_id,
                "amount_cents": pay.amount_cents,
                "billing_type": pay.billing_type,
                "status": pay.status,
                "invoice_url": pay.invoice_url,
                "received_at": pay.received_at,
                "archived_at": pay.archived_at,
                "created_at": pay.created_at,
                "updated_at": pay.updated_at,
                "client_name": client_name,
                "client_phone": client_phone,
                "professional_name": prof_name,
                "service_name": svc_name,
                "appointment_start": apt_start,
            })

        return payments, total

    def list_professionals(self) -> list[dict]:
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        professionals = self.db.query(Professional).all()

        result = []
        for prof in professionals:
            services_count = self.db.query(func.count(ProfessionalService.id)).filter(
                ProfessionalService.professional_id == prof.id,
                ProfessionalService.active.is_(True),
            ).scalar() or 0

            appointments_today = self.db.query(func.count(Appointment.id)).filter(
                and_(
                    Appointment.professional_id == prof.id,
                    func.date(Appointment.start_time) == today
                )
            ).scalar() or 0

            appointments_week = self.db.query(func.count(Appointment.id)).filter(
                and_(
                    Appointment.professional_id == prof.id,
                    func.date(Appointment.start_time) >= week_ago
                )
            ).scalar() or 0

            revenue_month = self.db.query(func.coalesce(func.sum(Payment.amount_cents), 0)).join(
                Appointment, Payment.appointment_id == Appointment.id
            ).filter(
                and_(
                    Appointment.professional_id == prof.id,
                    func.date(Appointment.start_time) >= month_ago,
                    Payment.status.in_(["received", "confirmed"])
                )
            ).scalar() or 0

            result.append({
                "id": prof.id,
                "name": prof.name,
                "phone": prof.phone,
                "email": prof.email,
                "bio": prof.bio,
                "photo_url": prof.photo_url,
                "active": prof.active,
                "services_count": services_count,
                "appointments_today": appointments_today,
                "appointments_week": appointments_week,
                "revenue_month_cents": int(revenue_month),
            })

        return result

    def _catalog_service_response(self, service: Service) -> dict:
        active_offerings_count = self.db.query(func.count(ProfessionalService.id)).filter(
            ProfessionalService.service_id == service.id,
            ProfessionalService.active.is_(True),
        ).scalar() or 0
        return {
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "category": service.category,
            "active": service.active,
            "active_offerings_count": active_offerings_count,
        }

    def list_catalog_services(self) -> list[dict]:
        services = self.db.query(Service).order_by(Service.active.desc(), Service.name).all()
        return [self._catalog_service_response(service) for service in services]

    def create_catalog_service(self, data) -> dict:
        service = ServiceCatalogService(self.db).create(
            name=data.name,
            description=data.description,
            category=data.category,
        )
        return self._catalog_service_response(service)

    def update_catalog_service(self, service_id: int, data) -> dict | None:
        values = data.model_dump(exclude_unset=True)
        service = ServiceCatalogService(self.db).update(service_id, **values)
        return self._catalog_service_response(service) if service else None

    def archive_or_delete_catalog_service(self, service_id: int) -> str | None:
        return ServiceCatalogService(self.db).archive_or_delete(service_id)

    def reactivate_catalog_service(self, service_id: int) -> dict | None:
        service = ServiceCatalogService(self.db).reactivate(service_id)
        return self._catalog_service_response(service) if service else None

    @staticmethod
    def _offering_response(offering: ProfessionalService) -> dict:
        return {
            "id": offering.id,
            "professional_id": offering.professional_id,
            "service_id": offering.service_id,
            "price_cents": offering.price_cents,
            "duration_minutes": offering.duration_minutes,
            "commission_percent": f"{offering.commission_percent:.2f}",
            "active": offering.active,
            "service_name": offering.service.name if offering.service else None,
            "service_description": (
                offering.service.description if offering.service else None
            ),
        }

    def get_professional_management(self, professional_id: int) -> dict | None:
        professional = self.db.get(Professional, professional_id)
        if not professional:
            return None
        offerings = (
            self.db.query(ProfessionalService)
            .filter(ProfessionalService.professional_id == professional_id)
            .order_by(ProfessionalService.id)
            .all()
        )
        availability = (
            self.db.query(Availability)
            .filter(Availability.professional_id == professional_id)
            .order_by(Availability.day_of_week, Availability.start_time)
            .all()
        )
        catalog = (
            self.db.query(Service)
            .filter(Service.active.is_(True))
            .order_by(Service.name)
            .all()
        )
        return {
            "professional": professional,
            "offerings": [self._offering_response(offering) for offering in offerings],
            "availability": availability,
            "catalog": catalog,
        }

    def save_professional_offering(self, professional_id: int, data) -> dict:
        offering = ProfessionalOfferingService(self.db).create_or_update(
            professional_id=professional_id,
            service_id=data.service_id,
            price_cents=data.price_cents,
            duration_minutes=data.duration_minutes,
            commission_percent=data.commission_percent,
        )
        return self._offering_response(offering)

    def remove_professional_offering(
        self, professional_id: int, service_id: int
    ) -> str | None:
        return ProfessionalOfferingService(self.db).archive_or_delete(
            professional_id, service_id
        )

    def archive_or_delete_professional(self, professional_id: int) -> str | None:
        return ProfessionalManagementService(self.db).archive_or_delete(professional_id)

    def _appointment_response(self, appointment: Appointment) -> dict:
        client = self.db.get(User, appointment.user_id)
        return {
            "id": appointment.id,
            "user_id": appointment.user_id,
            "professional_id": appointment.professional_id,
            "service_id": appointment.service_id,
            "start_time": appointment.start_time,
            "end_time": appointment.end_time,
            "status": appointment.status,
            "notes": appointment.notes,
            "service_price_cents": appointment.service_price_cents,
            "client_name": client.name if client else None,
            "client_phone": client.phone if client else None,
        }

    def create_appointment(self, data) -> dict:
        user_id = data.user_id
        if data.new_client:
            client = UserService(self.db).create(
                UserCreate(**data.new_client.model_dump())
            )
            user_id = client.id
        appointment = AppointmentService(self.db).create(
            AppointmentCreate(
                user_id=user_id,
                professional_id=data.professional_id,
                service_id=data.service_id,
                start_time=data.start_time,
                end_time=data.end_time,
                notes=data.notes,
            )
        )
        return self._appointment_response(appointment)

    def update_appointment(self, appointment_id: int, data) -> dict | None:
        appointment = self.db.get(Appointment, appointment_id)
        if not appointment:
            return None
        values = data.model_dump(exclude_unset=True)
        booking_fields = {
            "user_id",
            "professional_id",
            "service_id",
            "start_time",
            "end_time",
        }
        appointment_service = AppointmentService(self.db)
        if booking_fields.intersection(values):
            appointment = appointment_service.update_booking(
                appointment_id,
                AppointmentCreate(
                    user_id=values.get("user_id", appointment.user_id),
                    professional_id=values.get(
                        "professional_id", appointment.professional_id
                    ),
                    service_id=values.get("service_id", appointment.service_id),
                    start_time=values.get("start_time", appointment.start_time),
                    end_time=values.get("end_time", appointment.end_time),
                    notes=values.get("notes", appointment.notes),
                ),
            )
        elif "notes" in values:
            appointment = appointment_service.update(
                appointment_id, AppointmentUpdate(notes=values["notes"])
            )
        return self._appointment_response(appointment)

    def delete_appointment(self, appointment_id: int) -> bool:
        return AppointmentService(self.db).delete(appointment_id)

    def appointment_action(
        self, appointment_id: int, action: str, notes: str | None = None
    ) -> dict | None:
        try:
            appointment = AppointmentService(self.db).transition(
                appointment_id, action, notes
            )
        except ValueError as exc:
            return {"error": str(exc)}
        if not appointment:
            return None
        return {
            "id": appointment.id,
            "status": appointment.status,
            "notes": appointment.notes,
        }

    def get_appointment_detail(self, appointment_id: int) -> dict | None:
        latest_payment_id = (
            select(func.max(Payment.id))
            .where(Payment.appointment_id == Appointment.id)
            .correlate(Appointment)
            .scalar_subquery()
        )
        row = self.db.query(
            Appointment,
            User.name.label("client_name"),
            User.phone.label("client_phone"),
            User.email.label("client_email"),
            Professional.name.label("professional_name"),
            Professional.phone.label("professional_phone"),
            Service.name.label("service_name"),
            Service.duration_minutes.label("service_duration"),
            Service.price_cents.label("service_price_cents"),
            Payment.id.label("payment_id"),
            Payment.asaas_payment_id.label("payment_asaas_id"),
            Payment.amount_cents.label("payment_amount"),
            Payment.billing_type.label("payment_type"),
            Payment.status.label("payment_status"),
            Payment.invoice_url.label("payment_invoice_url"),
        ).outerjoin(User, Appointment.user_id == User.id).outerjoin(
            Professional, Appointment.professional_id == Professional.id
        ).outerjoin(Service, Appointment.service_id == Service.id).outerjoin(
            Payment, Payment.id == latest_payment_id
        ).filter(Appointment.id == appointment_id).first()

        if not row:
            return None

        apt, client_name, client_phone, client_email, prof_name, prof_phone, svc_name, svc_duration, svc_price, pay_id, pay_asaas_id, pay_amount, pay_type, pay_status, pay_invoice = row

        return {
            "appointment": {
                "id": apt.id,
                "start_time": apt.start_time,
                "end_time": apt.end_time,
                "status": apt.status,
                "expires_at": apt.expires_at,
                "notes": apt.notes,
                "created_at": apt.created_at,
            },
            "client": {
                "id": apt.user_id,
                "name": client_name,
                "phone": client_phone,
                "email": client_email,
            },
            "professional": {
                "id": apt.professional_id,
                "name": prof_name,
                "phone": prof_phone,
            },
            "service": {
                "id": apt.service_id,
                "name": svc_name,
                "duration_minutes": (
                    apt.service_duration_minutes
                    if apt.service_duration_minutes is not None
                    else svc_duration
                ),
                "price_cents": (
                    apt.service_price_cents
                    if apt.service_price_cents is not None
                    else svc_price
                ),
            },
            "payment": {
                "id": pay_id,
                "asaas_payment_id": pay_asaas_id,
                "amount_cents": pay_amount,
                "billing_type": pay_type,
                "status": pay_status,
                "invoice_url": pay_invoice,
            } if pay_id else None,
        }
