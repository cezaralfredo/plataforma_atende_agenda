from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.base import RelatedRecordsError
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.security import require_api_key
from app.services.user_service import UserService

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_api_key)],
)


@router.post("", response_model=UserRead, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    try:
        return UserService(db).create(data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[UserRead])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return UserService(db).repo.list(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = UserService(db).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user


@router.put("/{user_id}", response_model=UserRead)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    try:
        user = UserService(db).update(user_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    try:
        if not UserService(db).delete(user_id):
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
    except RelatedRecordsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
