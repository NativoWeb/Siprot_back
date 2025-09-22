from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import csv
import io

from models import User, Sector, CoreLine, DocumentType
from schemas import (
    SectorCreate, SectorUpdate, SectorResponse,
    CoreLineCreate, CoreLineUpdate, CoreLineResponse,
    DocumentTypeCreate, DocumentTypeUpdate, DocumentTypeResponse
)
from routers.auth import get_db, require_role
from routers.audit import AuditLogger, AuditAction, get_client_ip, get_user_agent

router = APIRouter(prefix="/catalogs", tags=["Catálogos Maestros"])

# ==================== SECTORES ====================

@router.post("/sectors", response_model=SectorResponse)
def create_sector(
    sector_data: SectorCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Crear un nuevo sector"""
    # Verificar que no exista
    if db.query(Sector).filter(Sector.name == sector_data.name).first():
        raise HTTPException(status_code=400, detail="Ya existe un sector con ese nombre")
    
    # Crear sector
    new_sector = Sector(
        **sector_data.dict(),
        created_by=current_user.id
    )
    db.add(new_sector)
    db.commit()
    db.refresh(new_sector)
    
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.CATALOG_SECTOR_CREATED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="SECTOR",
        target_id=str(new_sector.id),
        details={"sector_name": new_sector.name},
        request=request,
        new_values=sector_data.dict()
    )
    
    return SectorResponse.from_orm(new_sector)

@router.get("/sectors", response_model=List[SectorResponse])
def list_sectors(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo", "planeacion"]))
):
    """Listar todos los sectores"""
    query = db.query(Sector)
    if not include_inactive:
        query = query.filter(Sector.is_active == True)
    
    sectors = query.order_by(Sector.name).all()
    return [SectorResponse.from_orm(sector) for sector in sectors]

@router.put("/sectors/{sector_id}", response_model=SectorResponse)
def update_sector(
    sector_id: int,
    sector_data: SectorUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Actualizar un sector existente"""
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector no encontrado")
    
    # Guardar valores anteriores para auditoría
    old_values = {
        "name": sector.name,
        "description": sector.description,
        "is_active": sector.is_active
    }
    
    # Actualizar campos
    update_data = sector_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sector, field, value)
    
    db.commit()
    db.refresh(sector)
    
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.CATALOG_SECTOR_UPDATED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="SECTOR",
        target_id=str(sector.id),
        details={"sector_name": sector.name},
        request=request,
        old_values=old_values,
        new_values=update_data
    )
    
    return SectorResponse.from_orm(sector)

@router.delete("/sectors/{sector_id}")
def delete_sector(
    sector_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Desactivar un sector (soft delete)"""
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector no encontrado")
    
    if not sector.is_active:
        raise HTTPException(status_code=400, detail="El sector ya está inactivo")
    
    # Desactivar en lugar de eliminar
    sector.is_active = False
    db.commit()
    
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.CATALOG_SECTOR_DELETED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="SECTOR",
        target_id=str(sector.id),
        details={"sector_name": sector.name},
        request=request,
        old_values={"is_active": True},
        new_values={"is_active": False}
    )
    
    return {"message": f"Sector '{sector.name}' desactivado exitosamente"}

# ==================== LÍNEAS MEDULARES ====================

@router.get("/medular-lines", response_model=List[CoreLineResponse])
def list_medular_lines(
    include_inactive: bool = False,
    sector_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo", "planeacion"]))
):
    """Listar todas las líneas medulares (alias para core-lines)"""
    return list_core_lines(include_inactive, sector_id, db, current_user)

@router.post("/core-lines", response_model=CoreLineResponse)
def create_core_line(
    core_line_data: CoreLineCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Crear una nueva línea medular"""
    # Verificar que no exista
    if db.query(CoreLine).filter(CoreLine.name == core_line_data.name).first():
        raise HTTPException(status_code=400, detail="Ya existe una línea medular con ese nombre")
    
    # Verificar que el sector existe si se proporciona
    if core_line_data.sector_id:
        sector = db.query(Sector).filter(Sector.id == core_line_data.sector_id).first()
        if not sector:
            raise HTTPException(status_code=400, detail="El sector especificado no existe")
    
    # Crear línea medular
    core_line_dict = core_line_data.dict()
    # Remove created_by if it exists in the schema to avoid conflict
    core_line_dict.pop('created_by', None)
    
    new_core_line = CoreLine(
        **core_line_dict,
        created_by=current_user.id
    )
    db.add(new_core_line)
    db.commit()
    db.refresh(new_core_line)
    
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.CATALOG_CORE_LINE_CREATED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="CORE_LINE",
        target_id=str(new_core_line.id),
        details={"core_line_name": new_core_line.name},
        request=request,
        new_values=core_line_data.dict()
    )
    
    return CoreLineResponse.from_orm(new_core_line)

@router.get("/core-lines", response_model=List[CoreLineResponse])
def list_core_lines(
    include_inactive: bool = False,
    sector_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo", "planeacion"]))
):
    """Listar todas las líneas medulares"""
    query = db.query(CoreLine)
    
    if not include_inactive:
        query = query.filter(CoreLine.is_active == True)
    
    if sector_id:
        query = query.filter(CoreLine.sector_id == sector_id)
    
    core_lines = query.order_by(CoreLine.name).all()
    return [CoreLineResponse.from_orm(core_line) for core_line in core_lines]

@router.put("/core-lines/{core_line_id}", response_model=CoreLineResponse)
def update_core_line(
    core_line_id: int,
    core_line_data: CoreLineUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Actualizar una línea medular existente"""
    core_line = db.query(CoreLine).filter(CoreLine.id == core_line_id).first()
    if not core_line:
        raise HTTPException(status_code=404, detail="Línea medular no encontrada")
    
    # Guardar valores anteriores para auditoría
    old_values = {
        "name": core_line.name,
        "description": core_line.description,
        "sector_id": core_line.sector_id,
        "is_active": core_line.is_active
    }
    
    # Verificar que el sector existe si se proporciona
    update_data = core_line_data.dict(exclude_unset=True)
    if "sector_id" in update_data and update_data["sector_id"]:
        sector = db.query(Sector).filter(Sector.id == update_data["sector_id"]).first()
        if not sector:
            raise HTTPException(status_code=400, detail="El sector especificado no existe")
    
    # Actualizar campos
    for field, value in update_data.items():
        setattr(core_line, field, value)
    
    db.commit()
    db.refresh(core_line)
    
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.CATALOG_CORE_LINE_UPDATED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="CORE_LINE",
        target_id=str(core_line.id),
        details={"core_line_name": core_line.name},
        request=request,
        old_values=old_values,
        new_values=update_data
    )
    
    return CoreLineResponse.from_orm(core_line)

@router.delete("/core-lines/{core_line_id}")
def delete_core_line(
    core_line_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Desactivar una línea medular (soft delete)"""
    core_line = db.query(CoreLine).filter(CoreLine.id == core_line_id).first()
    if not core_line:
        raise HTTPException(status_code=404, detail="Línea medular no encontrada")
    
    if not core_line.is_active:
        raise HTTPException(status_code=400, detail="La línea medular ya está inactiva")
    
    # Desactivar en lugar de eliminar
    core_line.is_active = False
    db.commit()
    
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.CATALOG_CORE_LINE_DELETED,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="CORE_LINE",
        target_id=str(core_line.id),
        details={"core_line_name": core_line.name},
        request=request,
        old_values={"is_active": True},
        new_values={"is_active": False}
    )
    
    return {"message": f"Línea medular '{core_line.name}' desactivada exitosamente"}

# ==================== TIPOS DE DOCUMENTO ====================

@router.post("/document-types", response_model=DocumentTypeResponse)
def create_document_type(
    doc_type_data: DocumentTypeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Crear un nuevo tipo de documento"""
    # Verificar que no exista
    if db.query(DocumentType).filter(DocumentType.name == doc_type_data.name).first():
        raise HTTPException(status_code=400, detail="Ya existe un tipo de documento con ese nombre")
    
    doc_type_dict = doc_type_data.dict()
    # Remove created_by if it exists in the schema to avoid conflict
    doc_type_dict.pop('created_by', None)
    
    # Crear tipo de documento
    new_doc_type = DocumentType(
        **doc_type_dict,
        created_by=current_user.id
    )
    db.add(new_doc_type)
    db.commit()
    db.refresh(new_doc_type)
    
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.RESOURCE_CREATE,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="DOCUMENT_TYPE",
        target_id=str(new_doc_type.id),
        details={"document_type_name": new_doc_type.name},
        request=request,
        new_values=doc_type_data.dict()
    )
    
    return DocumentTypeResponse.from_orm(new_doc_type)

@router.get("/document-types", response_model=List[DocumentTypeResponse])
def list_document_types(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo", "planeacion"]))
):
    """Listar todos los tipos de documento"""
    query = db.query(DocumentType)
    if not include_inactive:
        query = query.filter(DocumentType.is_active == True)
    
    doc_types = query.order_by(DocumentType.name).all()
    return [DocumentTypeResponse.from_orm(doc_type) for doc_type in doc_types]

@router.put("/document-types/{doc_type_id}", response_model=DocumentTypeResponse)
def update_document_type(
    doc_type_id: int,
    doc_type_data: DocumentTypeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Actualizar un tipo de documento existente"""
    doc_type = db.query(DocumentType).filter(DocumentType.id == doc_type_id).first()
    if not doc_type:
        raise HTTPException(status_code=404, detail="Tipo de documento no encontrado")
    
    # Guardar valores anteriores para auditoría
    old_values = {
        "name": doc_type.name,
        "description": doc_type.description,
        "allowed_extensions": doc_type.allowed_extensions,
        "is_active": doc_type.is_active
    }
    
    # Actualizar campos
    update_data = doc_type_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(doc_type, field, value)
    
    db.commit()
    db.refresh(doc_type)
    
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.RESOURCE_UPDATE,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="DOCUMENT_TYPE",
        target_id=str(doc_type.id),
        details={"document_type_name": doc_type.name},
        request=request,
        old_values=old_values,
        new_values=update_data
    )
    
    return DocumentTypeResponse.from_orm(doc_type)

@router.delete("/document-types/{doc_type_id}")
def delete_document_type(
    doc_type_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """Desactivar un tipo de documento (soft delete)"""
    doc_type = db.query(DocumentType).filter(DocumentType.id == doc_type_id).first()
    if not doc_type:
        raise HTTPException(status_code=404, detail="Tipo de documento no encontrado")
    
    if not doc_type.is_active:
        raise HTTPException(status_code=400, detail="El tipo de documento ya está inactivo")
    
    # Desactivar en lugar de eliminar
    doc_type.is_active = False
    db.commit()
    
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.RESOURCE_DELETE,
        user_id=current_user.id,
        user_email=current_user.email,
        target_type="DOCUMENT_TYPE",
        target_id=str(doc_type.id),
        details={"document_type_name": doc_type.name},
        request=request,
        old_values={"is_active": True},
        new_values={"is_active": False}
    )
    
    return {"message": f"Tipo de documento '{doc_type.name}' desactivado exitosamente"}

@router.get("/document-types/export")
def export_document_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo", "planeacion"]))
):
    """Exportar tipos de documento a CSV"""
    # Obtener todos los tipos de documento activos
    doc_types = db.query(DocumentType).filter(DocumentType.is_active == True).order_by(DocumentType.name).all()
    
    # Crear CSV en memoria
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Escribir encabezados
    writer.writerow(['ID', 'Nombre', 'Descripción', 'Extensiones Permitidas', 'Fecha Creación', 'Creado Por'])
    
    # Escribir datos
    for doc_type in doc_types:
        writer.writerow([
            doc_type.id,
            doc_type.name,
            doc_type.description or '',
            ', '.join(doc_type.allowed_extensions) if doc_type.allowed_extensions else '',
            doc_type.created_at.strftime('%Y-%m-%d %H:%M:%S') if doc_type.created_at else '',
            doc_type.created_by or ''
        ])
    
    # Preparar respuesta
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type='text/csv',
        headers={"Content-Disposition": "attachment; filename=tipos_documentos.csv"}
    )

# ==================== ENDPOINTS COMBINADOS ====================

@router.get("/all")
def get_all_catalogs(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo", "planeacion"]))
):
    """Obtener todos los catálogos en una sola respuesta"""
    # Sectores
    sectors_query = db.query(Sector)
    if not include_inactive:
        sectors_query = sectors_query.filter(Sector.is_active == True)
    sectors = sectors_query.order_by(Sector.name).all()
    
    # Líneas medulares
    core_lines_query = db.query(CoreLine)
    if not include_inactive:
        core_lines_query = core_lines_query.filter(CoreLine.is_active == True)
    core_lines = core_lines_query.order_by(CoreLine.name).all()
    
    # Tipos de documento
    doc_types_query = db.query(DocumentType)
    if not include_inactive:
        doc_types_query = doc_types_query.filter(DocumentType.is_active == True)
    doc_types = doc_types_query.order_by(DocumentType.name).all()
    
    return {
        "sectors": [SectorResponse.from_orm(sector) for sector in sectors],
        "core_lines": [CoreLineResponse.from_orm(core_line) for core_line in core_lines],
        "document_types": [DocumentTypeResponse.from_orm(doc_type) for doc_type in doc_types]
    }
