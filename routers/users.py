from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from models import User
from schemas import UserCreate, UserResponse, UserUpdate
from routers.auth import get_db, get_password_hash, get_current_user, require_role, validate_role

router = APIRouter(prefix="/users", tags=["Usuarios"])

@router.post("/", response_model=UserResponse)
def create_user(user_data: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(require_role(["superadmin"]))):
    validate_role(user_data.role)

    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    hashed_password = get_password_hash(user_data.password)
    new_user = User(**user_data.dict(exclude={"password"}), password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserResponse.from_orm(new_user)

@router.get("/", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_role(["superadmin", "administrativo"]))):
    return [UserResponse.from_orm(user) for user in db.query(User).all()]

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.from_orm(current_user)

@router.put("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if current_user.role != "superadmin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="No autorizado")

    for field, value in user_data.dict(exclude_unset=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return UserResponse.from_orm(user)

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["superadmin"]))):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    db.delete(user)
    db.commit()
    return {"message": "Usuario eliminado exitosamente"}

@router.put("/{user_id}/password")
def change_password(user_id: int, password_data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "superadmin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="No autorizado")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    new_password = password_data.get("new_password")
    if not new_password:
        raise HTTPException(status_code=400, detail="Se requiere nueva contraseña")

    user.password = get_password_hash(new_password)
    db.commit()
    return {"message": "Contraseña actualizada exitosamente"}
