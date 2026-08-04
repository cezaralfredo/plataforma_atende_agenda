from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate
from app.services.service_service import ServiceService

router = APIRouter(prefix="/api/services", tags=["services"])


@router.post("", response_model=ServiceRead, status_code=201)
def create_service(data: ServiceCreate, db: Session = Depends(get_db)):
    service = ServiceService(db)
    return service.create(data)


@router.get("", response_model=list[ServiceRead])
def list_services(professional_id: int | None = None, category: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    service = ServiceService(db)
    return service.list(professional_id=professional_id, category=category, skip=skip, limit=limit)


@router.get("/{service_id}", response_model=ServiceRead)
def get_service(service_id: int, db: Session = Depends(get_db)):
    service = ServiceService(db)
    srv = service.get(service_id)
    if not srv:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    return srv


@router.put("/{service_id}", response_model=ServiceRead)
def update_service(service_id: int, data: ServiceUpdate, db: Session = Depends(get_db)):
    service = ServiceService(db)
    srv = service.update(service_id, data)
    if not srv:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    return srv


@router.delete("/{service_id}", status_code=204)
def delete_service(service_id: int, db: Session = Depends(get_db)):
    service = ServiceService(db)
    if not service.delete(service_id):
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
