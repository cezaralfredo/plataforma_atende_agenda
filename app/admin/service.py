from datetime import date, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.professional import Professional
from app.models.service import Service
from app.models.user import User


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
            Payment.status.in_(["pending", "confirmed"])
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
            Payment, Payment.appointment_id == Appointment.id
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
                "service_price_cents": svc_price,
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
            services_count = self.db.query(func.count(Service.id)).filter(
                Service.professional_id == prof.id
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

    def appointment_action(self, appointment_id: int, action: str, notes: str | None = None) -> dict | None:
        apt = self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not apt:
            return None

        if action == "cancel":
            if apt.status in ["cancelled", "completed"]:
                return {"error": "Não é possível cancelar agendamento neste status"}
            apt.status = "cancelled"
            if notes:
                apt.notes = (apt.notes or "") + f"\n[Admin] Cancelado: {notes}"
        elif action == "confirm":
            if apt.status != "pending":
                return {"error": "Só é possível confirmar agendamentos pendentes"}
            apt.status = "confirmed"
            if notes:
                apt.notes = (apt.notes or "") + f"\n[Admin] Confirmado: {notes}"
        else:
            return {"error": "Ação inválida"}

        self.db.commit()
        self.db.refresh(apt)

        return {
            "id": apt.id,
            "status": apt.status,
            "notes": apt.notes,
        }

    def payment_action(self, payment_id: int, action: str) -> dict | None:
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return None

        if action == "refresh":
            # TODO: Integrar com AsaasService para sincronizar status real
            return {"message": "Use o endpoint /api/payments/{id}/refresh para sincronizar com Asaas"}
        elif action == "refund":
            if payment.status not in ["received", "confirmed"]:
                return {"error": "Só é possível estornar pagamentos recebidos/confirmados"}
            payment.status = "refunded"
            self.db.commit()
            return {"id": payment.id, "status": payment.status}
        else:
            return {"error": "Ação inválida"}

    def get_appointment_detail(self, appointment_id: int) -> dict | None:
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
            Payment, Payment.appointment_id == Appointment.id
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
                "duration_minutes": svc_duration,
                "price_cents": svc_price,
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