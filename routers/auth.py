from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from models import User
from schemas import LoginRequest, LoginResponse, UserResponse
import logging
from routers.audit import AuditLogger, AuditAction
from dependencies import get_current_user, get_db

# 📌 Router
router = APIRouter(prefix="/auth", tags=["auth"])

# 🔐 Configuración de seguridad
SECRET_KEY = "tu-clave-secreta-muy-segura-aqui-cambiar-en-produccion"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 5      # Access token muy corto
REFRESH_TOKEN_EXPIRE_DAYS = 7        # Refresh token más largo

# Roles válidos
VALID_ROLES = ["superadmin", "administrativo", "planeacion", "instructor"]

# Contexto para encriptar/verificar
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# 🔑 Funciones para tokens
# ---------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ---------------------------------------------------------
# 🔐 Seguridad y utilidades
# ---------------------------------------------------------
def validate_role(role: str):
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rol inválido. Roles válidos: {', '.join(VALID_ROLES)}"
        )
    return role

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def require_role(allowed_roles: list[str]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker

# ---------------------------------------------------------
# 📌 Endpoints
# ---------------------------------------------------------

# 🔓 Login
@router.post("/login", response_model=LoginResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    logger.info(f"Intento de login para email: '{login_data.email}'")
    
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user:
        logger.warning(f"Login fallido: Usuario con email '{login_data.email}' no encontrado.")
        AuditLogger.log_action(
            db=db,
            action=AuditAction.USER_LOGIN_FAILED,
            user_email=login_data.email,
            resource_type="USER"
        )
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    if not verify_password(login_data.password, user.password):
        logger.warning(f"Login fallido: Contraseña incorrecta para '{user.email}'.")
        AuditLogger.log_user_action(
            db=db,
            action=AuditAction.USER_LOGIN_FAILED,
            user_id=user.id,
            user_email=user.email,
            resource_type="USER",
            resource_id=str(user.id)
        )
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    if not user.is_active:
        logger.warning(f"Login fallido: Usuario '{user.email}' está inactivo.")
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    
    # Log de login exitoso
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.USER_LOGIN,
        user_id=user.id,
        user_email=user.email,
        resource_type="USER",
        resource_id=str(user.id)
    )
    
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.email})
    
    logger.info(f"Login exitoso para '{user.email}'. Tokens generados.")
    
    return LoginResponse(
        message="Login exitoso",
        user=UserResponse.from_orm(user),
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

# 🔄 Refrescar token
@router.post("/refresh")
def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token inválido")
        
        user_email = payload.get("sub")
        if not user_email:
            raise HTTPException(status_code=401, detail="Token inválido")
        
        # Buscar usuario en la base de datos para obtener el rol
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        
        # Crear nuevo access token incluyendo rol
        new_access_token = create_access_token(data={"sub": user_email, "role": user.role})
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado")


