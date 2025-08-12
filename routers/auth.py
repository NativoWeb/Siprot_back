from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models import User
from database import SessionLocal
from schemas import LoginRequest, LoginResponse, UserResponse
import logging
from routers.audit import AuditLogger, AuditAction
from dependencies import get_current_user, get_db


# Se crea router para incluir en main.py
router = APIRouter(prefix="/auth", tags=["auth"])


# Configurar logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Configuración de seguridad
#
# Se crea una key para firmar el token
# Algoritmo de cifrado
# Tiempo de expiracion del token
#

SECRET_KEY = "tu-clave-secreta-muy-segura-aqui-cambiar-en-produccion"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # Tiempo de expiración del token en minutos


# Roles válidos

VALID_ROLES = ["superadmin", "administrativo", "planeacion", "instructor"]


# Contexto para encriptar/verificar
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


# Creacion de token JWT

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Funcion para validar que los Roles sea uno de los definidos en la variable VALID_ROLES

def validate_role(role: str):
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rol inválido. Roles válidos: {', '.join(VALID_ROLES)}"
        )
    return role


# Verificamos la contraseña comparandola en la base de datos al momento de autenticarse

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# Funcion para hashear la contraseña al momento de crear usuario

def get_password_hash(password):
    return pwd_context.hash(password)


# Verificacion de roles para acceder
# Retornamos una funcion que nos sirve para checkear los roles y proteger rutas

def require_role(allowed_roles: list[str]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker

# Endpoint de login
@router.post("/login", response_model=LoginResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    logger.info(f"Intento de login para email: '{login_data.email}'")
    
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user:
        logger.warning(f"Login fallido: Usuario con email '{login_data.email}' no encontrado.")
        # 📌 Log de intento fallido
        AuditLogger.log_action(
            db=db,
            action=AuditAction.USER_LOGIN_FAILED,
            user_email=login_data.email,
            resource_type="USER"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )
    
    logger.info(f"Usuario (Email: {user.email}) encontrado. ID: {user.id}, Rol: {user.role}, Activo: {user.is_active}")
    
    password_valid = verify_password(login_data.password, user.password)
    
    if not password_valid:
        logger.warning(f"Login fallido: Contraseña incorrecta para usuario '{user.email}'.")
        # 📌 Log de intento fallido
        AuditLogger.log_user_action(
            db=db,
            action=AuditAction.USER_LOGIN_FAILED,
            user_id=user.id,
            user_email=user.email,
            resource_type="USER",
            resource_id=str(user.id)
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )
    
    if not user.is_active:
        logger.warning(f"Login fallido: Usuario '{user.email}' está inactivo.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo"
        )
    
    # 📌 Log de login exitoso
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.USER_LOGIN,
        user_id=user.id,
        user_email=user.email,
        resource_type="USER",
        resource_id=str(user.id)
    )
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    logger.info(f"Login exitoso para usuario: '{user.email}'. Token generado.")
    
    return LoginResponse(
        message="Login exitoso",
        user=UserResponse.from_orm(user),
        access_token=access_token,
        token_type="bearer"
    )
