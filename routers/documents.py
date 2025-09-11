from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from models import Document, User
from schemas import DocumentResponse
from routers.auth import get_db, require_role
import os
import shutil
import uuid
import logging
import mimetypes
import unicodedata
import urllib.parse
from fastapi.responses import FileResponse
from datetime import datetime
from dependencies import get_current_user

router = APIRouter(prefix="/documents", tags=["Documentos"])

# Configuración de directorios
UPLOAD_DIRECTORY = "uploads"
DOCS_DIRECTORY = os.path.join(UPLOAD_DIRECTORY, "docs")  # Para PDF y DOCX
CSV_DIRECTORY = os.path.join(UPLOAD_DIRECTORY, "csv")    # Para XLSX y CSV

# Crear directorios si no existen
os.makedirs(DOCS_DIRECTORY, exist_ok=True)
os.makedirs(CSV_DIRECTORY, exist_ok=True)

logger = logging.getLogger(__name__)

# Tipos MIME permitidos y sus extensiones
ALLOWED_MIME_TYPES = {
    "application/pdf": DOCS_DIRECTORY,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DOCS_DIRECTORY,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": CSV_DIRECTORY,
    "text/csv": CSV_DIRECTORY
}

ALLOWED_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv'
}

def get_mime_type_from_extension(extension: str) -> str:
    """Obtiene el tipo MIME basado en la extensión del archivo"""
    mime_types = {
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.csv': 'text/csv'
    }
    return mime_types.get(extension.lower(), 'application/octet-stream')

def sanitize_filename(filename: str) -> str:
    """Limpia el nombre del archivo para que sea seguro"""
    if not filename:
        return "documento_sin_nombre"
    
    # Normalizar caracteres unicode
    filename = unicodedata.normalize('NFD', filename)

    # Filtrar caracteres no permitidos
    safe_chars = []
    for char in filename:
        if ord(char) < 32:
            continue
        elif ord(char) > 126:
            ascii_char = unicodedata.normalize('NFKD', char).encode('ascii', 'ignore').decode('ascii')
            safe_chars.append(ascii_char if ascii_char else '_')
        else:
            safe_chars.append(char)
    
    filename = ''.join(safe_chars)
    
    # Limpiar espacios y caracteres especiales
    import re
    filename = re.sub(r'[\s_-]+', '-', filename).strip('-_')
    
    if not filename:
        filename = "documento"
    
    # Limitar longitud
    return filename[:200]

def create_download_filename(title: str, original_name: str, extension: str) -> str:
    """Crea un nombre seguro para la descarga"""
    clean_title = sanitize_filename(title)
    clean_name = sanitize_filename(os.path.splitext(original_name)[0])
    
    if clean_title.lower() != clean_name.lower() and clean_name:
        filename = f"{clean_title}_{clean_name}{extension}"
    else:
        filename = f"{clean_title}{extension}"
    
    return filename[:250]  # Limitar longitud total

# Endpoint para subir documentos
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
    # Validar tipo de archivo
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de archivo no permitido. Formatos aceptados: PDF, DOCX, XLSX, CSV"
        )

    original_filename = file.filename or "documento_sin_nombre"
    file_extension = os.path.splitext(original_filename)[1].lower()
    
    # Validar extensión del archivo
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extensión {file_extension} no permitida. Use .pdf, .docx, .xlsx o .csv"
        )

    # Preparar directorio y nombre de archivo
    save_dir = ALLOWED_MIME_TYPES[file.content_type]
    unique_name = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.abspath(os.path.join(save_dir, unique_name))

    try:
        # Guardar archivo en disco
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error al guardar archivo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar el archivo en el servidor"
        )

    # Determinar tipo MIME real
    mime_type = get_mime_type_from_extension(file_extension)

    # Crear registro en la base de datos
    db_document = Document(
        title=title,
        original_filename=original_filename,
        file_extension=file_extension,
        mime_type=mime_type,
        year=year,
        sector=sector,
        core_line=core_line,
        document_type=document_type,
        additional_notes=additional_notes,
        file_path=file_path,
        uploaded_by_user_id=current_user.id
    )

    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    logger.info(f"Documento subido por {current_user.email}: ID {db_document.id}")
    return DocumentResponse.from_orm(db_document)

# Endpoint para listar documentos
@router.get("/", response_model=List[DocumentResponse])
def get_documents(
    search: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    core_line: Optional[str] = Query(None),
    document_type: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["administrativo", "planeacion", "superadmin", "instructor"]))
):
    query = db.query(Document)
    
    # Aplicar filtros
    if search:
        query = query.filter(Document.title.ilike(f"%{search}%"))
    if sector:
        query = query.filter(Document.sector == sector)
    if core_line:
        query = query.filter(Document.core_line == core_line)
    if document_type:
        query = query.filter(Document.document_type == document_type)
    if year:
        query = query.filter(Document.year == year)
    
    # Ordenar por fecha de subida descendente
    documents = query.order_by(Document.uploaded_at.desc()).all()
    logger.info(f"Se encontraron {len(documents)} documentos")
    
    return documents

# Endpoint para opciones de filtro
@router.get("/filter-options")
def get_filter_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["administrativo", "planeacion", "superadmin", "instructor"]))
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

# Endpoint para descargar documentos
@router.get("/download/{document_id}")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["administrativo", "planeacion", "superadmin", "instructor"]))
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )

    if not os.path.exists(document.file_path):
        logger.error(f"Archivo no encontrado: {document.file_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo no existe en el servidor"
        )

    # Crear nombre de descarga seguro
    download_name = create_download_filename(
        document.title,
        document.original_filename,
        document.file_extension
    )
    
    # Codificar nombre para headers
    encoded_name = urllib.parse.quote(download_name, safe='')
    
    return FileResponse(
        document.file_path,
        media_type=document.mime_type,
        filename=download_name,
        headers={
            "Content-Disposition": (
                f"attachment; "
                f"filename=\"{sanitize_filename(download_name)}\"; "
                f"filename*=UTF-8''{encoded_name}"
            ),
            "X-Document-Title": sanitize_filename(document.title),
            "X-File-Extension": document.file_extension
        }
    )

# Endpoint para actualizar metadatos
@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )

    # Actualizar campos
    document.title = title
    document.year = year
    document.sector = sector
    document.core_line = core_line
    document.document_type = document_type
    document.additional_notes = additional_notes

    db.commit()
    db.refresh(document)
    
    logger.info(f"Documento {document_id} actualizado por {current_user.email}")
    return DocumentResponse.from_orm(document)

# Endpoint para reemplazar archivo
@router.put("/{document_id}/file", response_model=DocumentResponse)
async def replace_file(
    document_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )

    # Validar tipo de archivo
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de archivo no permitido"
        )

    original_name = file.filename or "documento_sin_nombre"
    file_extension = os.path.splitext(original_name)[1].lower()
    
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extensión de archivo no permitida"
        )

    # Eliminar archivo anterior
    if os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception as e:
            logger.error(f"Error al eliminar archivo anterior: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al eliminar el archivo anterior"
            )

    # Guardar nuevo archivo
    save_dir = ALLOWED_MIME_TYPES[file.content_type]
    new_filename = f"{uuid.uuid4()}{file_extension}"
    new_path = os.path.join(save_dir, new_filename)

    try:
        with open(new_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error al guardar nuevo archivo: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar el nuevo archivo"
        )

    # Actualizar registro
    document.original_filename = original_name
    document.file_extension = file_extension
    document.mime_type = get_mime_type_from_extension(file_extension)
    document.file_path = new_path

    db.commit()
    db.refresh(document)
    
    logger.info(f"Archivo del documento {document_id} reemplazado por {current_user.email}")
    return DocumentResponse.from_orm(document)

# Endpoint para eliminar documentos
@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )

    # Eliminar archivo físico
    if os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except Exception as e:
            logger.error(f"Error al eliminar archivo: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al eliminar el archivo físico"
            )

    # Eliminar registro
    db.delete(document)
    db.commit()
    
    logger.info(f"Documento {document_id} eliminado por {current_user.email}")
    return {"detail": "Documento eliminado correctamente"}

# Endpoint para información detallada
@router.get("/{document_id}/info")
def document_info(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["administrativo", "planeacion", "superadmin"]))
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )

    file_size = os.path.getsize(document.file_path) if os.path.exists(document.file_path) else 0
    
    return {
        "id": document.id,
        "title": document.title,
        "original_filename": document.original_filename,
        "file_extension": document.file_extension,
        "mime_type": document.mime_type,
        "file_size": file_size,
        "download_filename": create_download_filename(
            document.title,
            document.original_filename,
            document.file_extension
        ),
        "uploaded_at": document.uploaded_at.isoformat()
    }