from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, func, ForeignKey
from sqlalchemy.orm import Session, relationship
from database import Base
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from enum import Enum
import logging
from models import AuditLog
from dependencies import get_current_user
# ==================== MODELOS DE AUDITORÍA ====================

class AuditAction(str, Enum):
    # Acciones de usuarios
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_PASSWORD_RESET = "user_password_reset"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_LIST_VIEWED = "user_list_viewed"
    
    # Acciones de documentos
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_DOWNLOADED = "document_downloaded"
    
    # Acciones de programas
    PROGRAM_CREATED = "program_created"
    PROGRAM_UPDATED = "program_updated"
    PROGRAM_DELETED = "program_deleted"
    
    # Acciones de reportes
    REPORT_GENERATED = "report_generated"
    REPORT_DOWNLOADED = "report_downloaded"
    REPORT_DELETED = "report_deleted"
    
    # Acciones de catálogos (R8.4)
    CATALOG_SECTOR_CREATED = "catalog_sector_created"
    CATALOG_SECTOR_UPDATED = "catalog_sector_updated"
    CATALOG_SECTOR_DELETED = "catalog_sector_deleted"
    CATALOG_CORE_LINE_CREATED = "catalog_core_line_created"
    CATALOG_CORE_LINE_UPDATED = "catalog_core_line_updated"
    CATALOG_CORE_LINE_DELETED = "catalog_core_line_deleted"
    
    # Acciones de configuración (R8.6)
    SYSTEM_CONFIG_UPDATED = "system_config_updated"


class AuditLogResponse(BaseModel):
    id: int
    action: str
    user_id: Optional[int]
    user_email: Optional[str]
    target_type: Optional[str]
    target_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime
    
    class Config:
        from_attributes = True

class AuditLogFilter(BaseModel):
    action: Optional[str] = None
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    target_type: Optional[str] = None
    resource_type: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 100
    offset: int = 0

# ==================== UTILIDADES DE AUDITORÍA ====================

class AuditLogger:
    """Clase para manejar el logging de auditoría"""
    
    @staticmethod
    def log_action(
        db: Session,
        action: AuditAction,
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Registra una acción en el log de auditoría"""

        # ✅ Si no viene resource_type/id, tomar target_type/id
        resource_type = resource_type or target_type
        resource_id = resource_id or target_id

        audit_log = AuditLog(
            action=action.value,
            user_id=user_id,
            user_email=user_email,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        
        logging.info(f"AUDIT: {action.value} by {user_email} on {target_type}:{target_id}")
        
        return audit_log
    
    @staticmethod
    def log_user_action(
        db: Session,
        action: AuditAction,
        user_id: int,
        user_email: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request = None
    ) -> AuditLog:
        """Registra una acción de usuario con información de la request"""
        
        ip_address = None
        user_agent = None
        
        if request:
            ip_address = request.client.host if hasattr(request, 'client') else None
            user_agent = request.headers.get("user-agent") if hasattr(request, 'headers') else None

        # ✅ Si no se pasa resource_type/id, tomarlos del target
        resource_type = resource_type or target_type
        resource_id = resource_id or target_id
        
        return AuditLogger.log_action(
            db=db,
            action=action,
            user_id=user_id,
            user_email=user_email,
            target_type=target_type,
            target_id=target_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent
        )


# ==================== ENDPOINTS DE AUDITORÍA ====================

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from models import User

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    action: Optional[str] = Query(None, description="Filtrar por acción específica"),
    user_email: Optional[str] = Query(None, description="Filtrar por email de usuario"),
    target_type: Optional[str] = Query(None, description="Filtrar por tipo de objetivo"),
    resource_type: Optional[str] = Query(None, description="Filtrar por tipo de recurso"),
    date_from: Optional[datetime] = Query(None, description="Fecha desde (YYYY-MM-DD HH:MM:SS)"),
    date_to: Optional[datetime] = Query(None, description="Fecha hasta (YYYY-MM-DD HH:MM:SS)"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene logs de auditoría (solo superadmin)"""
    
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Solo superadministradores pueden acceder a logs de auditoría")
    
    filters = AuditLogFilter(
        action=action,
        user_email=user_email,
        target_type=target_type,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset
    )
    
    logs = AuditLogger.get_audit_logs(db, filters)
    return logs

@router.get("/user/{user_id}/activity", response_model=List[AuditLogResponse])
async def get_user_activity(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene actividad de un usuario específico"""
    
    if current_user.role != "superadmin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="No tienes permisos para ver esta actividad")
    
    activity = AuditLogger.get_user_activity(db, user_id, limit)
    return activity

@router.get("/critical", response_model=List[AuditLogResponse])
async def get_critical_actions(
    hours: int = Query(24, ge=1, le=168, description="Horas hacia atrás para buscar"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene acciones críticas recientes (solo superadmin)"""
    
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Solo superadministradores pueden acceder a acciones críticas")
    
    critical_actions = AuditLogger.get_critical_actions(db, hours)
    return critical_actions

@router.get("/actions", response_model=List[str])
async def get_available_actions(
    current_user: User = Depends(get_current_user)
):
    """Obtiene lista de acciones disponibles para filtrar"""
    
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Solo superadministradores pueden acceder a esta información")
    
    return [action.value for action in AuditAction]

# ==================== CONFIGURACIÓN ====================

def setup_audit_logging():
    """Configura el logging de auditoría"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('audit.log'),
            logging.StreamHandler()
        ]
    )
