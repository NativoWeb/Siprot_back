from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from models import User, Permission, RolePermission
from schemas import PermissionResponse, RolePermissionCreate, RolePermissionResponse
from routers.auth import get_db, require_role, get_current_user
from routers.audit import AuditLogger, get_client_ip, get_user_agent

router = APIRouter(prefix="/permissions", tags=["Permisos y Roles"])

# Permisos predefinidos del sistema
DEFAULT_PERMISSIONS = [
    # Gestión de usuarios
    {"name": "users.create", "description": "Crear nuevos usuarios", "resource": "users", "action": "create"},
    {"name": "users.read", "description": "Ver información de usuarios", "resource": "users", "action": "read"},
    {"name": "users.update", "description": "Editar información de usuarios", "resource": "users", "action": "update"},
    {"name": "users.delete", "description": "Eliminar/desactivar usuarios", "resource": "users", "action": "delete"},
    {"name": "users.change_role", "description": "Cambiar roles de usuarios", "resource": "users", "action": "change_role"},
    
    # Gestión de documentos
    {"name": "documents.create", "description": "Subir nuevos documentos", "resource": "documents", "action": "create"},
    {"name": "documents.read", "description": "Ver y descargar documentos", "resource": "documents", "action": "read"},
    {"name": "documents.update", "description": "Editar información de documentos", "resource": "documents", "action": "update"},
    {"name": "documents.delete", "description": "Eliminar documentos", "resource": "documents", "action": "delete"},
    
    # Gestión de reportes
    {"name": "reports.create", "description": "Generar reportes", "resource": "reports", "action": "create"},
    {"name": "reports.read", "description": "Ver reportes generados", "resource": "reports", "action": "read"},
    {"name": "reports.delete", "description": "Eliminar reportes", "resource": "reports", "action": "delete"},
    
    # Gestión de programas
    {"name": "programs.create", "description": "Crear programas académicos", "resource": "programs", "action": "create"},
    {"name": "programs.read", "description": "Ver programas académicos", "resource": "programs", "action": "read"},
    {"name": "programs.update", "description": "Editar programas académicos", "resource": "programs", "action": "update"},
    {"name": "programs.delete", "description": "Eliminar programas académicos", "resource": "programs", "action": "delete"},
    
    # Gestión de catálogos maestros
    {"name": "catalogs.create", "description": "Crear elementos en catálogos", "resource": "catalogs", "action": "create"},
    {"name": "catalogs.read", "description": "Ver catálogos maestros", "resource": "catalogs", "action": "read"},
    {"name": "catalogs.update", "description": "Editar catálogos maestros", "resource": "catalogs", "action": "update"},
    {"name": "catalogs.delete", "description": "Eliminar elementos de catálogos", "resource": "catalogs", "action": "delete"},
    
    # Configuración del sistema
    {"name": "system_config.read", "description": "Ver configuración del sistema", "resource": "system_config", "action": "read"},
    {"name": "system_config.update", "description": "Modificar configuración del sistema", "resource": "system_config", "action": "update"},
    
    # Auditoría
    {"name": "audit.read", "description": "Ver logs de auditoría", "resource": "audit", "action": "read"},
    
    # Gestión de permisos
    {"name": "permissions.read", "description": "Ver permisos del sistema", "resource": "permissions", "action": "read"},
    {"name": "permissions.manage", "description": "Gestionar permisos de roles", "resource": "permissions", "action": "manage"},
]

# Permisos por rol por defecto
DEFAULT_ROLE_PERMISSIONS = {
    "superadmin": [
        # Superadmin tiene todos los permisos
        "users.create", "users.read", "users.update", "users.delete", "users.change_role",
        "documents.create", "documents.read", "documents.update", "documents.delete",
        "reports.create", "reports.read", "reports.delete",
        "programs.create", "programs.read", "programs.update", "programs.delete",
        "catalogs.create", "catalogs.read", "catalogs.update", "catalogs.delete",
        "system_config.read", "system_config.update",
        "audit.read",
        "permissions.read", "permissions.manage"
    ],
    "administrativo": [
        # Administrativo puede gestionar usuarios y ver reportes
        "users.create", "users.read", "users.update", "users.change_role",
        "documents.read",
        "reports.create", "reports.read",
        "programs.read",
        "catalogs.read",
        "audit.read"
    ],
    "planeacion": [
        # Planeación puede gestionar documentos y programas
        "documents.create", "documents.read", "documents.update", "documents.delete",
        "reports.create", "reports.read",
        "programs.create", "programs.read", "programs.update", "programs.delete",
        "catalogs.read"
    ],
    "instructor": [
        # Instructor solo puede ver documentos y generar reportes básicos
        "documents.read",
        "reports.create", "reports.read",
        "programs.read",
        "catalogs.read"
    ]
}

def user_has_permission(db: Session, user: User, permission_name: str) -> bool:
    """
    Verifica si un usuario tiene un permiso específico
    """
    # Buscar el permiso
    permission = db.query(Permission).filter(Permission.name == permission_name).first()
    if not permission:
        return False
    
    # Buscar si el rol del usuario tiene este permiso
    role_permission = db.query(RolePermission).filter(
        RolePermission.role == user.role,
        RolePermission.permission_id == permission.id,
        RolePermission.granted == True
    ).first()
    
    return role_permission is not None

def require_permission(permission_name: str):
    """
    Decorador para requerir un permiso específico
    """
    def permission_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if not user_has_permission(db, current_user, permission_name):
            raise HTTPException(
                status_code=403,
                detail=f"Permiso requerido: {permission_name}"
            )
        return current_user
    return permission_checker

@router.post("/initialize")
def initialize_permissions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """
    Inicializar permisos y asignaciones por defecto
    """
    created_permissions = 0
    created_role_permissions = 0
    
    # Crear permisos si no existen
    for perm_data in DEFAULT_PERMISSIONS:
        existing_perm = db.query(Permission).filter(Permission.name == perm_data["name"]).first()
        if not existing_perm:
            new_permission = Permission(**perm_data)
            db.add(new_permission)
            created_permissions += 1
    
    db.commit()
    
    # Asignar permisos a roles
    for role, permission_names in DEFAULT_ROLE_PERMISSIONS.items():
        for perm_name in permission_names:
            permission = db.query(Permission).filter(Permission.name == perm_name).first()
            if permission:
                # Verificar si ya existe la asignación
                existing_assignment = db.query(RolePermission).filter(
                    RolePermission.role == role,
                    RolePermission.permission_id == permission.id
                ).first()
                
                if not existing_assignment:
                    role_permission = RolePermission(
                        role=role,
                        permission_id=permission.id,
                        granted=True,
                        created_by=current_user.id
                    )
                    db.add(role_permission)
                    created_role_permissions += 1
    
    db.commit()
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_action(
        action="INITIALIZE_PERMISSIONS",
        resource_type="PERMISSIONS",
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        details=f"Inicializados {created_permissions} permisos y {created_role_permissions} asignaciones"
    )
    
    return {
        "message": "Permisos inicializados exitosamente",
        "created_permissions": created_permissions,
        "created_role_permissions": created_role_permissions
    }

@router.get("/", response_model=List[PermissionResponse])
def list_permissions(
    resource: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo"]))
):
    """
    Listar todos los permisos disponibles
    """
    query = db.query(Permission)
    
    if resource:
        query = query.filter(Permission.resource == resource)
    
    permissions = query.order_by(Permission.resource, Permission.action).all()
    return [PermissionResponse.from_orm(perm) for perm in permissions]

@router.get("/resources")
def list_resources(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo"]))
):
    """
    Listar todos los recursos disponibles
    """
    resources = db.query(Permission.resource).distinct().all()
    return {"resources": [res[0] for res in resources]}

@router.get("/roles/{role}/permissions", response_model=List[PermissionResponse])
def get_role_permissions(
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo"]))
):
    """
    Obtener todos los permisos asignados a un rol específico
    """
    # Validar que el rol existe
    valid_roles = ["superadmin", "administrativo", "planeacion", "instructor"]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail="Rol inválido")
    
    # Obtener permisos del rol
    role_permissions = db.query(RolePermission).filter(
        RolePermission.role == role,
        RolePermission.granted == True
    ).all()
    
    permissions = []
    for rp in role_permissions:
        permission = db.query(Permission).filter(Permission.id == rp.permission_id).first()
        if permission:
            permissions.append(permission)
    
    return [PermissionResponse.from_orm(perm) for perm in permissions]

@router.post("/roles/{role}/permissions")
def assign_permission_to_role(
    role: str,
    permission_data: RolePermissionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """
    Asignar un permiso a un rol
    """
    # Validar que el rol existe
    valid_roles = ["superadmin", "administrativo", "planeacion", "instructor"]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail="Rol inválido")
    
    # Validar que el permiso existe
    permission = db.query(Permission).filter(Permission.id == permission_data.permission_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permiso no encontrado")
    
    # Verificar si ya existe la asignación
    existing_assignment = db.query(RolePermission).filter(
        RolePermission.role == role,
        RolePermission.permission_id == permission_data.permission_id
    ).first()
    
    if existing_assignment:
        # Actualizar si es diferente
        if existing_assignment.granted != permission_data.granted:
            old_value = existing_assignment.granted
            existing_assignment.granted = permission_data.granted
            existing_assignment.created_by = current_user.id
            db.commit()
            
            # Log de auditoría
            audit = AuditLogger(db)
            audit.log_action(
                action="UPDATE_ROLE_PERMISSION",
                resource_type="ROLE_PERMISSION",
                user_id=current_user.id,
                resource_id=f"{role}:{permission.name}",
                old_values={"granted": old_value},
                new_values={"granted": permission_data.granted},
                ip_address=get_client_ip(request),
                details=f"Permiso {permission.name} {'otorgado' if permission_data.granted else 'revocado'} para rol {role}"
            )
            
            return {"message": f"Permiso {'otorgado' if permission_data.granted else 'revocado'} exitosamente"}
        else:
            return {"message": "El permiso ya tiene el estado solicitado"}
    else:
        # Crear nueva asignación
        role_permission = RolePermission(
            role=role,
            permission_id=permission_data.permission_id,
            granted=permission_data.granted,
            created_by=current_user.id
        )
        db.add(role_permission)
        db.commit()
        
        # Log de auditoría
        audit = AuditLogger(db)
        audit.log_action(
            action="CREATE_ROLE_PERMISSION",
            resource_type="ROLE_PERMISSION",
            user_id=current_user.id,
            resource_id=f"{role}:{permission.name}",
            new_values={"granted": permission_data.granted},
            ip_address=get_client_ip(request),
            details=f"Permiso {permission.name} {'otorgado' if permission_data.granted else 'revocado'} para rol {role}"
        )
        
        return {"message": f"Permiso {'otorgado' if permission_data.granted else 'revocado'} exitosamente"}

@router.delete("/roles/{role}/permissions/{permission_id}")
def remove_permission_from_role(
    role: str,
    permission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """
    Remover completamente un permiso de un rol
    """
    # Validar que el rol existe
    valid_roles = ["superadmin", "administrativo", "planeacion", "instructor"]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail="Rol inválido")
    
    # Buscar la asignación
    role_permission = db.query(RolePermission).filter(
        RolePermission.role == role,
        RolePermission.permission_id == permission_id
    ).first()
    
    if not role_permission:
        raise HTTPException(status_code=404, detail="Asignación de permiso no encontrada")
    
    # Obtener información del permiso para auditoría
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    
    # Eliminar asignación
    db.delete(role_permission)
    db.commit()
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_action(
        action="DELETE_ROLE_PERMISSION",
        resource_type="ROLE_PERMISSION",
        user_id=current_user.id,
        resource_id=f"{role}:{permission.name if permission else permission_id}",
        old_values={"granted": role_permission.granted},
        ip_address=get_client_ip(request),
        details=f"Asignación de permiso eliminada para rol {role}"
    )
    
    return {"message": "Asignación de permiso eliminada exitosamente"}

@router.get("/user/{user_id}/permissions")
def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo"]))
):
    """
    Obtener todos los permisos efectivos de un usuario específico
    """
    # Verificar que el usuario existe
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Obtener permisos del rol del usuario
    role_permissions = db.query(RolePermission).filter(
        RolePermission.role == user.role,
        RolePermission.granted == True
    ).all()
    
    permissions = []
    for rp in role_permissions:
        permission = db.query(Permission).filter(Permission.id == rp.permission_id).first()
        if permission:
            permissions.append(permission)
    
    return {
        "user_id": user_id,
        "user_email": user.email,
        "user_role": user.role,
        "permissions": [PermissionResponse.from_orm(perm) for perm in permissions]
    }

@router.get("/check/{permission_name}")
def check_current_user_permission(
    permission_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verificar si el usuario actual tiene un permiso específico
    """
    has_permission = user_has_permission(db, current_user, permission_name)
    
    return {
        "user_id": current_user.id,
        "permission": permission_name,
        "granted": has_permission
    }
