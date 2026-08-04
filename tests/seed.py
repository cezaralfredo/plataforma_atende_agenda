from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.availability import Availability
from app.models.payment import Payment
from app.models.professional import Professional
from app.models.service import Service
from app.models.user import User


def seed_data(db: Session) -> dict:
    user = User(
        name="João Silva",
        phone="+5511999999999",
        email="joao@email.com",
        created_at="2026-07-29T10:00:00",
    )
    db.add(user)
    db.flush()

    professional = Professional(
        name="Maria Souza",
        phone="+5511988888888",
        email="maria@email.com",
        bio="Cabeleireira profissional",
        active=True,
    )
    db.add(professional)
    db.flush()

    service = Service(
        professional_id=professional.id,
        name="Corte de cabelo",
        description="Corte masculino e feminino",
        duration_minutes=60,
        price_cents=5000,
        category="corte",
    )
    db.add(service)
    db.flush()

    service2 = Service(
        professional_id=professional.id,
        name="Escova",
        description="Escova modeladora",
        duration_minutes=45,
        price_cents=3500,
        category="escova",
    )
    db.add(service2)
    db.flush()

    availability = Availability(
        professional_id=professional.id,
        day_of_week=2,
        start_time="08:00",
        end_time="12:00",
    )
    db.add(availability)

    availability2 = Availability(
        professional_id=professional.id,
        day_of_week=2,
        start_time="13:00",
        end_time="18:00",
    )
    db.add(availability2)

    availability3 = Availability(
        professional_id=professional.id,
        specific_date="2026-07-30",
        start_time="09:00",
        end_time="17:00",
    )
    db.add(availability3)

    db.commit()

    return {
        "user": user,
        "professional": professional,
        "service": service,
        "service2": service2,
        "availability": availability,
    }


def seed_appointment(db: Session, entities: dict) -> Appointment:
    apt = Appointment(
        user_id=entities["user"].id,
        professional_id=entities["professional"].id,
        service_id=entities["service"].id,
        start_time="2026-07-30T09:00:00",
        end_time="2026-07-30T10:00:00",
        status="awaiting_payment",
        created_at="2026-07-29T10:00:00",
        expires_at="2026-07-29T10:30:00",
    )
    db.add(apt)
    db.commit()
    db.flush()
    return apt


def seed_payment(db: Session, appointment: Appointment) -> Payment:
    from datetime import datetime

    pay = Payment(
        appointment_id=appointment.id,
        asaas_payment_id="pay_abc123",
        amount_cents=5000,
        billing_type="pix",
        status="pending",
        invoice_url="https://asaas.com/pay/abc123",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    db.add(pay)
    db.commit()
    db.flush()
    return pay
