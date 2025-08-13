from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from models import User, Sector, CoreLine, DocumentType
from schemas import (
    SectorCreate, SectorUpdate, SectorResponse,
    CoreLineCreate, CoreLineUpdate, CoreLineResponse,
    DocumentTypeCreate, DocumentTypeUpdate, DocumentTypeResponse
)
from routers.auth import get_db, require_role
from routers.audit import AuditLogger, get_client_ip, get_user_agent

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
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_catalog_change(
        action="CREATE",
        catalog_type="SECTOR",
        catalog_id=new_sector.id,
        new_data=sector_data.dict(),
        user_id=current_user.id,
        ip=get_client_ip(request)
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
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_catalog_change(
        action="UPDATE",
        catalog_type="SECTOR",
        catalog_id=sector.id,
        old_data=old_values,
        new_data=update_data,
        user_id=current_user.id,
        ip=get_client_ip(request)
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
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_catalog_change(
        action="DELETE",
        catalog_type="SECTOR",
        catalog_id=sector.id,
        old_data={"is_active": True},
        new_data={"is_active": False},
        user_id=current_user.id,
        ip=get_client_ip(request)
    )
    
    return {"message": f"Sector '{sector.name}' desactivado exitosamente"}

# ==================== LÍNEAS MEDULARES ====================

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
    new_core_line = CoreLine(
        **core_line_data.dict(),
        created_by=current_user.id
    )
    db.add(new_core_line)
    db.commit()
    db.refresh(new_core_line)
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_catalog_change(
        action="CREATE",
        catalog_type="CORE_LINE",
        catalog_id=new_core_line.id,
        new_data=core_line_data.dict(),
        user_id=current_user.id,
        ip=get_client_ip(request)
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
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_catalog_change(
        action="UPDATE",
        catalog_type="CORE_LINE",
        catalog_id=core_line.id,
        old_data=old_values,
        new_data=update_data,
        user_id=current_user.id,
        ip=get_client_ip(request)
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
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_catalog_change(
        action="DELETE",
        catalog_type="CORE_LINE",
        catalog_id=core_line.id,
        old_data={"is_active": True},
        new_data={"is_active": False},
        user_id=current_user.id,
        ip=get_client_ip(request)
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
    
    # Crear tipo de documento
    new_doc_type = DocumentType(
        **doc_type_data.dict(),
        created_by=current_user.id
    )
    db.add(new_doc_type)
    db.commit()
    db.refresh(new_doc_type)
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_catalog_change(
        action="CREATE",
        catalog_type="DOCUMENT_TYPE",
        catalog_id=new_doc_type.id,
        new_data=doc_type_data.dict(),
        user_id=current_user.id,
        ip=get_client_ip(request)
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
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_catalog_change(
        action="UPDATE",
        catalog_type="DOCUMENT_TYPE",
        catalog_id=doc_type.id,
        old_data=old_values,
        new_data=update_data,
        user_id=current_user.id,
        ip=get_client_ip(request)
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
    
    # Log de auditoría
    audit = AuditLogger(db)
    audit.log_catalog_change(
        action="DELETE",
        catalog_type="DOCUMENT_TYPE",
        catalog_id=doc_type.id,
        old_data={"is_active": True},
        new_data={"is_active": False},
        user_id=current_user.id,
        ip=get_client_ip(request)
    )
    
    return {"message": f"Tipo de documento '{doc_type.name}' desactivado exitosamente"}

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
