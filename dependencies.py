from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from database import SessionLocal
from models import User
import logging

logger = logging.getLogger(__name__)

SECRET_KEY = "tu-clave-secreta-muy-segura-aqui-cambiar-en-produccion"
ALGORITHM = "HS256"

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    logger.info(f"[v0] Attempting to validate token: {credentials.credentials[:20]}...")
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        logger.info(f"Token decoded successfully, user_email: {user_email}")
        
        if user_email is None:
            logger.warning("No user email found in token payload")
            raise credentials_exception
    except JWTError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise credentials_exception

    user = db.query(User).filter(User.email == user_email).first()
    if user is None:
        logger.warning(f"User not found in database: {user_email}")
        raise credentials_exception
    
    logger.info(f"User authenticated successfully: {user.email}, role: {user.role}")
    return user
