from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from models import Document, User
from schemas import DocumentResponse
from routers.auth import get_db, require_role
import os, shutil, uuid
import logging
import mimetypes
import unicodedata
import urllib.parse
from fastapi.responses import FileResponse

router = APIRouter(prefix="/documents", tags=["Documentos"])

# Directorios de almacenamiento de archivos
UPLOAD_DIRECTORY = "uploads"
DOCS_DIRECTORY = os.path.join(UPLOAD_DIRECTORY, "docs")  # PDF y DOCX
CSV_DIRECTORY = os.path.join(UPLOAD_DIRECTORY, "csv")    # XLSX y CSV

# Crear carpetas si no existen
os.makedirs(DOCS_DIRECTORY, exist_ok=True)
os.makedirs(CSV_DIRECTORY, exist_ok=True)

# Logger para errores del sistema
logger = logging.getLogger(__name__)

# Asociación de tipos MIME con su carpeta destino
ALLOWED_MIME_TYPES = {
    "application/pdf": DOCS_DIRECTORY,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DOCS_DIRECTORY,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": CSV_DIRECTORY,
    "text/csv": CSV_DIRECTORY
}

def get_mime_type_from_extension(file_extension: str) -> str:
    """Obtiene el tipo MIME basado en la extensión del archivo"""
    mime_types = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.csv': 'text/csv',
        '.doc': 'application/msword',
        '.xls': 'application/vnd.ms-excel'
    }
    return mime_types.get(file_extension.lower(), 'application/octet-stream')

def sanitize_filename(filename: str) -> str:
    """
    Limpia el nombre del archivo para que sea seguro para el sistema de archivos
    y compatible con diferentes codificaciones
    """
    if not filename:
        return "documento"
    
    filename = unicodedata.normalize('NFD', filename)
    
    replacements = {
        '–': '-',
        '—': '-',
        ''': "'",
        ''': "'",
        '"': '"',
        '"': '"',
        '…': '...',
        '«': '"',
        '»': '"',
    }
    
    for old, new in replacements.items():
        filename = filename.replace(old, new)
    
    safe_chars = []
    for char in filename:
        if ord(char) < 32:
            continue
        elif ord(char) > 126:
            ascii_char = unicodedata.normalize('NFKD', char).encode('ascii', 'ignore').decode('ascii')
            if ascii_char:
                safe_chars.append(ascii_char)
            else:
                safe_chars.append('_')
        elif char in '<>:"/\\|?*':
            safe_chars.append('_')
        else:
            safe_chars.append(char)
    
    filename = ''.join(safe_chars)
    
    import re
    filename = re.sub(r'[\s_-]+', '-', filename)
    filename = filename.strip(' -_')
    
    if not filename:
        filename = "documento"
    
    if len(filename) > 100:
        filename = filename[:100]
    
    return filename

def create_safe_download_filename(title: str, original_filename: str, extension: str) -> str:
    title_clean = sanitize_filename(title)
    original_name = os.path.splitext(original_filename)[0]
    original_name_clean = sanitize_filename(original_name)
    
    if title_clean.lower() != original_name_clean.lower() and len(original_name_clean) > 0:
        download_filename = f"{title_clean}_{original_name_clean}{extension}"
    else:
        download_filename = f"{title_clean}{extension}"
    
    if len(download_filename) > 200:
        download_filename = f"{title_clean[:100]}{extension}"
    
    return download_filename

# 📥 Cargar nuevo documento
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
        raise HTTPException(status_code=400, detail="Formato no permitido. Use PDF, DOCX, XLSX o CSV.")

    original_filename = file.filename or "documento_sin_nombre"
    file_extension = os.path.splitext(original_filename)[1].lower()
    
    # Validar extensión
    allowed_extensions = ['.pdf', '.docx', '.xlsx', '.csv']
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extensión de archivo no permitida. Use .pdf, .docx, .xlsx o .csv"
        )

    save_directory = ALLOWED_MIME_TYPES[file.content_type]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_location = os.path.join(save_directory, unique_filename)

    # Guardar archivo en disco
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Archivo '{original_filename}' guardado localmente en: {file_location}")
    except Exception as e:
        logger.error(f"Error guardando archivo: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar el archivo.")

    # Obtener tipo MIME correcto
    mime_type = get_mime_type_from_extension(file_extension)

    # Registrar documento en la base de datos
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
        file_path=file_location,
        uploaded_by_user_id=current_user.id
    )

    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return DocumentResponse.from_orm(db_document)
# 📄 Listar documentos con filtros opcionales
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
    
    documents = query.all()
    logger.info(f"Se encontraron {len(documents)} documentos con los filtros aplicados.")
    
    return [DocumentResponse.from_orm(doc) for doc in documents]

# 📊 Obtener opciones de filtro dinámicas
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

# 📥 Descargar documento
@router.get("/download/{document_id}")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["administrativo", "planeacion", "superadmin"]))
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    
    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor.")

    logger.info(f"Usuario {current_user.email} descargando documento ID: {document_id}")
    
    download_filename = create_safe_download_filename(
        document.title, 
        document.original_filename, 
        document.file_extension
    )
    
    encoded_filename = urllib.parse.quote(download_filename, safe='')
    
    return FileResponse(
        path=document.file_path, 
        filename=download_filename, 
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{sanitize_filename(download_filename)}\"; filename*=UTF-8''{encoded_filename}",
            "X-Original-Filename": sanitize_filename(document.original_filename),
            "X-Document-Title": sanitize_filename(document.title)
        }
    )

# ✏️ Editar metadatos del documento
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

# 🔁 Reemplazar archivo de un documento existente
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

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Formato no permitido. Use PDF, DOCX, XLSX o CSV.")

    # Eliminar archivo anterior si existe
    if os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
            logger.info(f"Archivo físico eliminado: {document.file_path}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo anterior: {e}")

    # Guardar nuevo archivo
    original_filename = file.filename or "documento_sin_nombre"
    file_extension = os.path.splitext(original_filename)[1].lower()
    save_directory = ALLOWED_MIME_TYPES[file.content_type]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_location = os.path.join(save_directory, unique_filename)

    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Nuevo archivo guardado en: {file_location}")
    except Exception as e:
        logger.error(f"Error guardando archivo: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar el nuevo archivo.")

    # Actualizar metadatos del archivo
    document.file_path = file_location
    document.original_filename = original_filename
    document.file_extension = file_extension
    document.mime_type = get_mime_type_from_extension(file_extension)

    db.commit()
    db.refresh(document)

    return DocumentResponse.from_orm(document)

# 🗑️ Eliminar documento
@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Eliminar archivo físico
    if os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
            logger.info(f"Archivo físico eliminado: {document.file_path}")
        except Exception as e:
            logger.error(f"Error al eliminar archivo físico: {e}")

    # Eliminar registro de la base de datos
    db.delete(document)
    db.commit()
    
    logger.info(f"Documento con ID {document_id} eliminado por {current_user.email}")

    return {"detail": "Documento eliminado con éxito"}

# ℹ️ Obtener información del documento
@router.get("/{document_id}/info")
def get_document_info(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["administrativo", "planeacion", "superadmin"]))
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    file_size = 0
    if os.path.exists(document.file_path):
        file_size = os.path.getsize(document.file_path)
    
    return {
        "id": document.id,
        "title": document.title,
        "original_filename": document.original_filename,
        "file_extension": document.file_extension,
        "mime_type": document.mime_type,
        "file_size": file_size,
        "download_filename": create_safe_download_filename(
            document.title, 
            document.original_filename, 
            document.file_extension
        )
    }