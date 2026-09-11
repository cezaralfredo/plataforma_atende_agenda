from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.professional import Professional
from app.models.professional_service import ProfessionalService
from app.models.service import Service
from app.schemas.professional_service import ProfessionalServiceCreate
from app.schemas.service import ServiceCreate


def test_company_owns_service_terms_and_professional_link_owns_commission(
    db_session: Session,
):
    """Moving commercial terms back to a professional must break this contract."""
    service = Service(
        name="Corte feminino",
        description="Corte personalizado",
        category="Cabelo",
        duration_minutes=60,
        price_cents=9000,
        active=True,
    )
    professional = Professional(name="Ana", active=True)
    db_session.add_all([service, professional])
    db_session.flush()

    assignment = ProfessionalService(
        professional_id=professional.id,
        service_id=service.id,
    )
    db_session.add(assignment)
    db_session.commit()

    assert service.price_cents == 9000
    assert service.duration_minutes == 60
    assert assignment.commission_percent == Decimal("10.00")
    assert not hasattr(Service, "professional_id")
    assert not hasattr(ProfessionalService, "price_cents")
    assert not hasattr(ProfessionalService, "duration_minutes")


def test_catalog_and_assignment_contracts_keep_their_responsibilities_separate():
    """Adding professional commercial terms back to assignments must break this contract."""
    service = ServiceCreate(
        name="Corte feminino",
        duration_minutes=60,
        price_cents=9000,
    )
    assignment = ProfessionalServiceCreate(service_id=7)

    assert service.price_cents == 9000
    assert service.duration_minutes == 60
    assert not hasattr(service, "professional_id")
    assert assignment.commission_percent == Decimal("10.00")
    assert not hasattr(assignment, "price_cents")
    assert not hasattr(assignment, "duration_minutes")
