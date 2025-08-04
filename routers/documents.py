from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from models import Document, User
from schemas import DocumentResponse
from routers.auth import get_db, require_role
import os, shutil, uuid
import logging

router = APIRouter(prefix="/documents", tags=["Documentos"])

# Configuración de directorio y logging
UPLOAD_DIRECTORY = "uploads"
logger = logging.getLogger(__name__)

# Endpoint: Cargar Documento
@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    year: int = Form(...),
    sector: str = Form(...),
    core_line: str = Form(...),
    document_type: str = Form(...),
    additional_notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Formato no permitido. Use PDF, DOCX o XLSX.")

    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_location = os.path.join(UPLOAD_DIRECTORY, unique_filename)

    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error guardando archivo: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar el archivo.")

    db_document = Document(
        title=title,
        year=year,
        sector=sector,
        core_line=core_line,
        document_type=document_type,
        additional_notes=additional_notes,
        file_path=file_location,
        uploaded_by_user_id=current_user.id
    )

    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    return DocumentResponse.from_orm(db_document)

# Listar documentos con filtros
@router.get("/", response_model=List[DocumentResponse])
def get_documents(
    sector: Optional[str] = Query(None),
    core_line: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["administrativo", "planeacion", "superadmin"]))
):
    query = db.query(Document)
    if sector:
        query = query.filter(Document.sector == sector)
    if core_line:
        query = query.filter(Document.core_line == core_line)
    if document_type:
        query = query.filter(Document.document_type == document_type)
    if year:
        query = query.filter(Document.year == year)
    if search:
        query = query.filter(Document.title.ilike(f"%{search}%"))
    query = query.order_by(Document.uploaded_at.desc())
    return [DocumentResponse.from_orm(doc) for doc in query.all()]

# Opciones para filtros
@router.get("/filter-options")
def get_document_filter_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["administrativo", "planeacion", "superadmin"]))
):
    sectors = db.query(Document.sector).distinct().all()
    core_lines = db.query(Document.core_line).distinct().all()
    document_types = db.query(Document.document_type).distinct().all()
    years = db.query(Document.year).distinct().order_by(Document.year.desc()).all()

    return {
        "sectors": [s[0] for s in sectors if s[0]],
        "core_lines": [c[0] for c in core_lines if c[0]],
        "document_types": [d[0] for d in document_types if d[0]],
        "years": [y[0] for y in years if y[0]]
    }

# ✅ NUEVO: Editar metadatos
@router.put("/{document_id}/edit", response_model=DocumentResponse)
def update_document_metadata(
    document_id: int,
    title: str = Form(...),
    year: int = Form(...),
    sector: str = Form(...),
    core_line: str = Form(...),
    document_type: str = Form(...),
    additional_notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    document.title = title
    document.year = year
    document.sector = sector
    document.core_line = core_line
    document.document_type = document_type
    document.additional_notes = additional_notes

    db.commit()
    db.refresh(document)
    return DocumentResponse.from_orm(document)

# ✅ NUEVO: Reemplazar archivo
@router.put("/{document_id}/replace-file", response_model=DocumentResponse)
async def replace_document_file(
    document_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Formato no permitido. Use PDF, DOCX o XLSX.")

    # Eliminar archivo anterior
    if os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo anterior: {e}")

    # Guardar nuevo archivo
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_location = os.path.join(UPLOAD_DIRECTORY, unique_filename)

    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error guardando archivo: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar el nuevo archivo.")

    # Actualizar en BD
    document.file_path = file_location
    db.commit()
    db.refresh(document)

    return DocumentResponse.from_orm(document)
