"""Inicializa o banco de dados SQLite local com tabelas e dados de exemplo."""

import sys
from datetime import UTC, datetime, time, timedelta

from app.database import Base, SessionLocal, engine
from app.models.appointment import Appointment
from app.models.availability import Availability
from app.models.payment import Payment
from app.models.professional import Professional
from app.models.service import Service
from app.models.user import User


def init_db():
    print("Criando tabelas no banco de dados...")
    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas com sucesso!")

    db = SessionLocal()
    try:
        # Verificar se já existem profissionais
        if db.query(Professional).first():
            print("Banco de dados já contém registros. Pulando seed.")
            return

        print("Populando dados de demonstração...")

        # 1. Usuários / Clientes
        user1 = User(
            name="João Silva",
            phone="+5511999999999",
            email="joao@email.com",
            whatsapp_number="5511999999999",
        )
        user2 = User(
            name="Ana Oliveira",
            phone="+5511977777777",
            email="ana@email.com",
            whatsapp_number="5511977777777",
        )
        db.add_all([user1, user2])
        db.flush()

        # 2. Profissionais
        prof1 = Professional(
            name="Maria Souza",
            phone="+5511988888888",
            email="maria@email.com",
            bio="Especialista em cortes, visagismo e coloração",
            active=True,
        )
        prof2 = Professional(
            name="Carlos Barbeiro",
            phone="+5511966666666",
            email="carlos@email.com",
            bio="Especialista em barba, cabelo e estética masculina",
            active=True,
        )
        db.add_all([prof1, prof2])
        db.flush()

        # 3. Serviços
        srv1 = Service(
            professional_id=prof1.id,
            name="Corte Feminino",
            description="Corte, lavagem e finalização",
            duration_minutes=60,
            price_cents=8000,
            category="cabelo",
        )
        srv2 = Service(
            professional_id=prof1.id,
            name="Escova Modeladora",
            description="Lavagem e escova modeladora",
            duration_minutes=45,
            price_cents=5000,
            category="cabelo",
        )
        srv3 = Service(
            professional_id=prof2.id,
            name="Corte Masculino + Barba",
            description="Corte degrade navalhado e barba na toalha quente",
            duration_minutes=60,
            price_cents=7000,
            category="barbearia",
        )
        db.add_all([srv1, srv2, srv3])
        db.flush()

        # 4. Disponibilidades (Segunda a Sexta - 08:00 às 18:00)
        for day in range(0, 6):  # 0=Segunda ... 5=Sábado
            db.add(Availability(
                professional_id=prof1.id,
                day_of_week=day,
                start_time=time(8, 0),
                end_time=time(12, 0),
            ))
            db.add(Availability(
                professional_id=prof1.id,
                day_of_week=day,
                start_time=time(13, 0),
                end_time=time(18, 0),
            ))
            db.add(Availability(
                professional_id=prof2.id,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(19, 0),
            ))
        db.flush()

        # 5. Agendamentos de exemplo
        now = datetime.now(UTC)
        tomorrow_10am = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        apt1 = Appointment(
            user_id=user1.id,
            professional_id=prof1.id,
            service_id=srv1.id,
            start_time=tomorrow_10am,
            end_time=tomorrow_10am + timedelta(minutes=60),
            status="confirmed",
            notes="Primeira visita da cliente",
            created_at=now,
        )
        db.add(apt1)
        db.flush()

        pay1 = Payment(
            appointment_id=apt1.id,
            asaas_payment_id="pay_demo_pix_1",
            amount_cents=8000,
            billing_type="pix",
            status="confirmed",
            invoice_url="https://sandbox.asaas.com/i/demo1",
            created_at=now,
            updated_at=now,
        )
        db.add(pay1)

        db.commit()
        print("Dados de demonstração criados com sucesso!")
        print(f"- 2 Usuários: {user1.name}, {user2.name}")
        print(f"- 2 Profissionais: {prof1.name}, {prof2.name}")
        print(f"- 3 Serviços cadastrados")
        print(f"- 1 Agendamento de exemplo confirmado")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
