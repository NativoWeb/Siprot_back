from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json
import os
from pathlib import Path

from models import User, SystemConfiguration
from schemas import SystemConfigurationCreate, SystemConfigurationUpdate, SystemConfigurationResponse
from routers.auth import get_db, require_role
from routers.audit import AuditLogger, get_client_ip, get_user_agent

router = APIRouter(prefix="/system-config", tags=["Configuración del Sistema"])

# Configuraciones predefinidas del sistema
DEFAULT_CONFIGURATIONS = {
    # Textos de la interfaz
    "app_title": {
        "value": "Sistema SIPROT",
        "data_type": "string",
        "description": "Título principal de la aplicación",
        "category": "ui",
        "is_public": True
    },
    "app_subtitle": {
        "value": "Sistema de Información para la Prospectiva Tecnológica",
        "data_type": "string", 
        "description": "Subtítulo de la aplicación",
        "category": "ui",
        "is_public": True
    },
    "welcome_message": {
        "value": "Bienvenido al Sistema SIPROT del SENA",
        "data_type": "string",
        "description": "Mensaje de bienvenida en la página principal",
        "category": "ui",
        "is_public": True
    },
    "footer_text": {
        "value": "© 2024 SENA - Servicio Nacional de Aprendizaje",
        "data_type": "string",
        "description": "Texto del pie de página",
        "category": "ui",
        "is_public": True
    },
    
    # Configuraciones de archivos
    "max_file_size_mb": {
        "value": "50",
        "data_type": "integer",
        "description": "Tamaño máximo de archivo en MB",
        "category": "files",
        "is_public": False
    },
    "allowed_file_extensions": {
        "value": '["pdf", "docx", "xlsx", "pptx", "txt"]',
        "data_type": "json",
        "description": "Extensiones de archivo permitidas",
        "category": "files",
        "is_public": False
    },
    
    # Configuraciones de email
    "support_email": {
        "value": "soporte@sena.edu.co",
        "data_type": "string",
        "description": "Email de soporte técnico",
        "category": "email",
        "is_public": True
    },
    "admin_email": {
        "value": "admin@sena.edu.co",
        "data_type": "string",
        "description": "Email del administrador del sistema",
        "category": "email",
        "is_public": False
    },
    
    # Configuraciones de seguridad
    "session_timeout_minutes": {
        "value": "30",
        "data_type": "integer",
        "description": "Tiempo de expiración de sesión en minutos",
        "category": "security",
        "is_public": False
    },
    "password_min_length": {
        "value": "8",
        "data_type": "integer",
        "description": "Longitud mínima de contraseña",
        "category": "security",
        "is_public": False
    },
    
    # Configuraciones de reportes
    "default_report_format": {
        "value": "pdf",
        "data_type": "string",
        "description": "Formato por defecto para reportes",
        "category": "reports",
        "is_public": False
    },
    
    # Configuraciones institucionales
    "institution_name": {
        "value": "SENA - Servicio Nacional de Aprendizaje",
        "data_type": "string",
        "description": "Nombre completo de la institución",
        "category": "institution",
        "is_public": True
    },
    "institution_logo_url": {
        "value": "/static/images/sena-logo.png",
        "data_type": "string",
        "description": "URL del logotipo institucional",
        "category": "institution",
        "is_public": True
    }
}

def get_config_value(db: Session, key: str, default_value: Any = None) -> Any:
    """
    Obtiene el valor de una configuración, con conversión de tipo automática
    """
    config = db.query(SystemConfiguration).filter(SystemConfiguration.key == key).first()
    
    if not config:
        return default_value
    
    # Convertir según el tipo de dato
    if config.data_type == "integer":
        try:
            return int(config.value)
        except (ValueError, TypeError):
            return default_value
    elif config.data_type == "boolean":
        return config.value.lower() in ("true", "1", "yes", "on")
    elif config.data_type == "json":
        try:
            return json.loads(config.value)
        except (json.JSONDecodeError, TypeError):
            return default_value
    else:  # string
        return config.value

@router.post("/initialize")
def initialize_default_configs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """
    Inicializar configuraciones por defecto del sistema
    """
    created_count = 0
    updated_count = 0
    
    for key, config_data in DEFAULT_CONFIGURATIONS.items():
        existing_config = db.query(SystemConfiguration).filter(SystemConfiguration.key == key).first()
        
        if not existing_config:
            # Crear nueva configuración
            new_config = SystemConfiguration(
                key=key,
                value=config_data["value"],
                data_type=config_data["data_type"],
                description=config_data["description"],
                category=config_data["category"],
                is_public=config_data["is_public"],
                updated_by=current_user.id
            )
            db.add(new_config)
            created_count += 1
        else:
            # Actualizar descripción y categoría si han cambiado
            if (existing_config.description != config_data["description"] or 
                existing_config.category != config_data["category"]):
                existing_config.description = config_data["description"]
                existing_config.category = config_data["category"]
                existing_config.updated_by = current_user.id
                updated_count += 1
    
    db.commit()
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_action(
        action="INITIALIZE_SYSTEM_CONFIG",
        resource_type="SYSTEM_CONFIG",
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        details=f"Inicializadas {created_count} configuraciones nuevas, actualizadas {updated_count}"
    )
    
    return {
        "message": "Configuraciones inicializadas exitosamente",
        "created": created_count,
        "updated": updated_count
    }

@router.get("/", response_model=List[SystemConfigurationResponse])
def list_configurations(
    category: Optional[str] = None,
    include_private: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo"]))
):
    """
    Listar todas las configuraciones del sistema
    """
    query = db.query(SystemConfiguration)
    
    if category:
        query = query.filter(SystemConfiguration.category == category)
    
    # Solo superadmin puede ver configuraciones privadas
    if not include_private or current_user.role != "superadmin":
        query = query.filter(SystemConfiguration.is_public == True)
    
    configs = query.order_by(SystemConfiguration.category, SystemConfiguration.key).all()
    return [SystemConfigurationResponse.from_orm(config) for config in configs]

@router.get("/public")
def get_public_configurations(db: Session = Depends(get_db)):
    """
    Obtener configuraciones públicas (sin autenticación requerida)
    """
    configs = db.query(SystemConfiguration).filter(SystemConfiguration.is_public == True).all()
    
    result = {}
    for config in configs:
        # Convertir valor según tipo
        if config.data_type == "integer":
            try:
                result[config.key] = int(config.value)
            except (ValueError, TypeError):
                result[config.key] = config.value
        elif config.data_type == "boolean":
            result[config.key] = config.value.lower() in ("true", "1", "yes", "on")
        elif config.data_type == "json":
            try:
                result[config.key] = json.loads(config.value)
            except (json.JSONDecodeError, TypeError):
                result[config.key] = config.value
        else:
            result[config.key] = config.value
    
    return result

@router.get("/categories")
def get_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo"]))
):
    """
    Obtener todas las categorías de configuración disponibles
    """
    categories = db.query(SystemConfiguration.category).distinct().all()
    return {"categories": [cat[0] for cat in categories if cat[0]]}

@router.post("/", response_model=SystemConfigurationResponse)
def create_configuration(
    config_data: SystemConfigurationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """
    Crear una nueva configuración del sistema
    """
    # Verificar que no exista
    if db.query(SystemConfiguration).filter(SystemConfiguration.key == config_data.key).first():
        raise HTTPException(status_code=400, detail="Ya existe una configuración con esa clave")
    
    # Validar valor según tipo de dato
    if config_data.data_type == "integer":
        try:
            int(config_data.value)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Valor inválido para tipo integer")
    elif config_data.data_type == "json":
        try:
            json.loads(config_data.value)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Valor inválido para tipo JSON")
    
    # Crear configuración
    new_config = SystemConfiguration(
        **config_data.dict(),
        updated_by=current_user.id
    )
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_action(
        action="CREATE_SYSTEM_CONFIG",
        resource_type="SYSTEM_CONFIG",
        user_id=current_user.id,
        resource_id=config_data.key,
        new_values=config_data.dict(),
        ip_address=get_client_ip(request),
        details=f"Configuración creada: {config_data.key}"
    )
    
    return SystemConfigurationResponse.from_orm(new_config)

@router.put("/{config_key}", response_model=SystemConfigurationResponse)
def update_configuration(
    config_key: str,
    config_data: SystemConfigurationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """
    Actualizar una configuración existente
    """
    config = db.query(SystemConfiguration).filter(SystemConfiguration.key == config_key).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    
    # Guardar valores anteriores para auditoría
    old_values = {
        "value": config.value,
        "description": config.description,
        "category": config.category,
        "is_public": config.is_public
    }
    
    # Validar nuevo valor según tipo de dato
    update_data = config_data.dict(exclude_unset=True)
    if "value" in update_data:
        if config.data_type == "integer":
            try:
                int(update_data["value"])
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Valor inválido para tipo integer")
        elif config.data_type == "json":
            try:
                json.loads(update_data["value"])
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Valor inválido para tipo JSON")
    
    # Actualizar campos
    for field, value in update_data.items():
        setattr(config, field, value)
    
    config.updated_by = current_user.id
    db.commit()
    db.refresh(config)
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_action(
        action="UPDATE_SYSTEM_CONFIG",
        resource_type="SYSTEM_CONFIG",
        user_id=current_user.id,
        resource_id=config_key,
        old_values=old_values,
        new_values=update_data,
        ip_address=get_client_ip(request),
        details=f"Configuración actualizada: {config_key}"
    )
    
    return SystemConfigurationResponse.from_orm(config)

@router.delete("/{config_key}")
def delete_configuration(
    config_key: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """
    Eliminar una configuración del sistema
    """
    config = db.query(SystemConfiguration).filter(SystemConfiguration.key == config_key).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    
    # Prevenir eliminación de configuraciones críticas
    critical_configs = ["app_title", "institution_name", "session_timeout_minutes"]
    if config_key in critical_configs:
        raise HTTPException(
            status_code=400, 
            detail="No se puede eliminar esta configuración crítica del sistema"
        )
    
    # Guardar datos para auditoría
    old_values = {
        "key": config.key,
        "value": config.value,
        "data_type": config.data_type,
        "description": config.description,
        "category": config.category,
        "is_public": config.is_public
    }
    
    db.delete(config)
    db.commit()
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_action(
        action="DELETE_SYSTEM_CONFIG",
        resource_type="SYSTEM_CONFIG",
        user_id=current_user.id,
        resource_id=config_key,
        old_values=old_values,
        ip_address=get_client_ip(request),
        details=f"Configuración eliminada: {config_key}"
    )
    
    return {"message": f"Configuración '{config_key}' eliminada exitosamente"}

@router.post("/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """
    Subir logotipo institucional
    """
    # Validar tipo de archivo
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Tipo de archivo no permitido. Use JPEG, PNG, GIF o WebP"
        )
    
    # Validar tamaño (máximo 5MB)
    max_size = 5 * 1024 * 1024  # 5MB
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(status_code=400, detail="El archivo es demasiado grande (máximo 5MB)")
    
    # Crear directorio si no existe
    upload_dir = Path("uploads/logos")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generar nombre único para el archivo
    file_extension = file.filename.split(".")[-1].lower()
    new_filename = f"logo_institucional.{file_extension}"
    file_path = upload_dir / new_filename
    
    # Guardar archivo
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Actualizar configuración
    logo_url = f"/static/logos/{new_filename}"
    config = db.query(SystemConfiguration).filter(SystemConfiguration.key == "institution_logo_url").first()
    
    old_value = config.value if config else None
    
    if config:
        config.value = logo_url
        config.updated_by = current_user.id
    else:
        config = SystemConfiguration(
            key="institution_logo_url",
            value=logo_url,
            data_type="string",
            description="URL del logotipo institucional",
            category="institution",
            is_public=True,
            updated_by=current_user.id
        )
        db.add(config)
    
    db.commit()
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_action(
        action="UPLOAD_LOGO",
        resource_type="SYSTEM_CONFIG",
        user_id=current_user.id,
        resource_id="institution_logo_url",
        old_values={"value": old_value} if old_value else None,
        new_values={"value": logo_url},
        ip_address=get_client_ip(request) if request else None,
        details=f"Logotipo institucional actualizado: {new_filename}"
    )
    
    return {
        "message": "Logotipo subido exitosamente",
        "logo_url": logo_url,
        "filename": new_filename
    }
