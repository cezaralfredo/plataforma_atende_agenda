from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.professional import (
    ProfessionalCreate,
    ProfessionalRead,
    ProfessionalUpdate,
)
from app.services.professional_service import ProfessionalService

router = APIRouter(prefix="/api/professionals", tags=["professionals"])


@router.post("", response_model=ProfessionalRead, status_code=201)
def create_professional(data: ProfessionalCreate, db: Session = Depends(get_db)):
    service = ProfessionalService(db)
    return service.create(data)


@router.get("", response_model=list[ProfessionalRead])
def list_professionals(active_only: bool = False, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = ProfessionalService(db)
    return service.list(skip=skip, limit=limit, active_only=active_only)


@router.get("/{professional_id}", response_model=ProfessionalRead)
def get_professional(professional_id: int, db: Session = Depends(get_db)):
    service = ProfessionalService(db)
    prof = service.get(professional_id)
    if not prof:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    return prof


@router.put("/{professional_id}", response_model=ProfessionalRead)
def update_professional(professional_id: int, data: ProfessionalUpdate, db: Session = Depends(get_db)):
    service = ProfessionalService(db)
    prof = service.update(professional_id, data)
    if not prof:
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
    return prof


@router.delete("/{professional_id}", status_code=204)
def delete_professional(professional_id: int, db: Session = Depends(get_db)):
    service = ProfessionalService(db)
    if not service.delete(professional_id):
        raise HTTPException(status_code=404, detail="Profissional não encontrado")
