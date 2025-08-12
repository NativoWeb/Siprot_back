from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from models import User
from schemas import UserCreate, UserResponse, UserUpdate
from routers.auth import get_password_hash, require_role, validate_role
from dependencies import get_current_user, get_db
from routers.audit import AuditLogger, AuditAction  # ✅ Importar para auditoría

router = APIRouter(prefix="/users", tags=["Usuarios"])

@router.post("/", response_model=UserResponse)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"])),
    request: Request = None
):
    validate_role(user_data.role)

    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    hashed_password = get_password_hash(user_data.password)
    new_user = User(**user_data.dict(exclude={"password"}), password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 🔹 Auditoría (movemos target_* a details)
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.USER_CREATED,
        user_id=current_user.id,
        user_email=current_user.email,
        details={
            "created_user_email": new_user.email,
            "target_type": "user",
            "target_id": new_user.id
        },
        request=request
    )

    return UserResponse.from_orm(new_user)

@router.get("/", response_model=List[UserResponse])
def list_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo"]))
):
    users = db.query(User).all()

    # ✅ Log de auditoría
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.USER_LIST_VIEWED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="user",
        details={"total_users": len(users)},
        request=request
    )

    return [UserResponse.from_orm(user) for user in users]

@router.get("/me", response_model=UserResponse)
def get_me(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # ✅ Log de auditoría
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.USER_PROFILE_VIEWED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="user",
        target_id=current_user.id,
        request=request
    )
    return UserResponse.from_orm(current_user)

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    request: Request,
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if current_user.role != "superadmin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="No autorizado")

    update_data = user_data.dict(exclude_unset=True)

    if "password" in update_data:
        user.password = get_password_hash(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    # ✅ Log de auditoría
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.USER_UPDATED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="user",
        target_id=user.id,
        details=update_data,
        request=request
    )

    return UserResponse.from_orm(user)

@router.delete("/{user_id}")
def delete_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user.role in ["planeacion", "superadmin"]:
        raise HTTPException(
            status_code=400,
            detail='Los usuarios del rol "planeacion" y "superadmin" al tener archivos vinculados no se pueden eliminar. '
                   'En caso que ya no quiera que se use un usuario, lo mejor es quitar el estado activo.'
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="El usuario ya está inactivo")

    user.is_active = False
    db.commit()

    # ✅ Log de auditoría
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.USER_DEACTIVATED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="user",
        target_id=user.id,
        details={"deactivated_user_email": user.email},
        request=request
    )

    return {"message": f"Usuario '{user.email}' desactivado exitosamente"}

@router.put("/{user_id}/password")
def change_password(
    request: Request,
    user_id: int,
    password_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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

    # ✅ Log de auditoría
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.USER_PASSWORD_CHANGED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="user",
        target_id=user.id,
        details={"changed_user_email": user.email},
        request=request
    )

    return {"message": "Contraseña actualizada exitosamente"}
