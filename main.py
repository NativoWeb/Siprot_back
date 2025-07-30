from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import SessionLocal, engine
from models import User, Base, Document
from schemas import LoginRequest, LoginResponse, UserCreate, UserResponse, UserUpdate, DocumentCreate, DocumentResponse
from auth import (
    verify_password, get_password_hash, create_access_token, 
    get_current_user, require_role, get_db, validate_role, VALID_ROLES
)
from fastapi.middleware.cors import CORSMiddleware
from datetime import timedelta
import logging
import os
import shutil
import uuid

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directorio para guardar los archivos subidos
UPLOAD_DIRECTORY = "uploads"

# Crear las tablas
Base.metadata.create_all(bind=engine)

# Asegurarse de que el directorio de subidas exista
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)
    logger.info(f"Directorio de subidas '{UPLOAD_DIRECTORY}' creado.")

app = FastAPI(title="Sistema de Gestión de Usuarios SIPROT", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambiar en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint de login
@app.post("/login", response_model=LoginResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    logger.info(f"Intento de login para email: '{login_data.email}'")
    
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user:
        logger.warning(f"Login fallido: Usuario con email '{login_data.email}' no encontrado.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )
    
    logger.info(f"Usuario (Email: {user.email}) encontrado. ID: {user.id}, Rol: {user.role}, Activo: {user.is_active}")
    
    password_valid = verify_password(login_data.password, user.password)
    
    if not password_valid:
        logger.warning(f"Login fallido: Contraseña incorrecta para usuario '{user.email}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )
    
    logger.info(f"Contraseña para '{user.email}' verificada correctamente.")
    
    if not user.is_active:
        logger.warning(f"Login fallido: Usuario '{user.email}' está inactivo.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo"
        )
    
    logger.info(f"Usuario '{user.email}' está activo.")
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role},
        expires_delta=access_token_expires
    )
    
    logger.info(f"Login exitoso para usuario: '{user.email}'. Token generado.")
    
    return LoginResponse(
        message="Login exitoso",
        user=UserResponse.from_orm(user),
        access_token=access_token,
        token_type="bearer"
    )

# Endpoint para debugging - verificar usuarios
@app.get("/debug/users", response_model=List[UserResponse])
def debug_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [UserResponse.from_orm(user) for user in users]

# Endpoint para verificar contraseña específica
@app.post("/debug/verify-password")
def debug_verify_password(data: dict, db: Session = Depends(get_db)):
    email = data.get("email")
    password = data.get("password")
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"error": "Usuario no encontrado"}
    
    is_valid = verify_password(password, user.password)
    
    return {
        "email": email,
        "password_provided": password,
        "stored_hash_prefix": user.password[:20] + "...",
        "is_valid": is_valid,
        "user_active": user.is_active
    }

# Crear usuario (solo superadmin)
@app.post("/users", response_model=UserResponse)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    validate_role(user_data.role)
    
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=user_data.email,
        password=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone_number=user_data.phone_number,
        additional_notes=user_data.additional_notes,
        role=user_data.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse.from_orm(db_user)

# Listar usuarios (superadmin y administrativo)
@app.get("/users", response_model=List[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "administrativo"]))
):
    users = db.query(User).all()
    return [UserResponse.from_orm(user) for user in users]

# Obtener usuario actual
@app.get("/users/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return UserResponse.from_orm(current_user)

# Actualizar usuario
@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "superadmin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para actualizar este usuario"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    if user_data.email and user_data.email != user.email:
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El nuevo email ya está registrado por otro usuario"
            )

    if user_data.role and current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para cambiar roles"
        )
    
    if user_data.role:
        validate_role(user_data.role)
    
    for field, value in user_data.dict(exclude_unset=True).items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return UserResponse.from_orm(user)

# Eliminar usuario (solo superadmin)
@app.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propio usuario"
        )
    
    db.delete(user)
    db.commit()
    
    return {"message": "Usuario eliminado exitosamente"}

# Obtener roles disponibles
@app.get("/roles")
def get_roles():
    return {"roles": VALID_ROLES}

# Cambiar contraseña
@app.put("/users/{user_id}/password")
def change_password(
    user_id: int,
    password_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "superadmin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para cambiar esta contraseña"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    new_password = password_data.get("new_password")
    if not new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña es requerida"
        )
    
    user.password = get_password_hash(new_password)
    db.commit()
    
    return {"message": "Contraseña actualizada exitosamente"}

# Endpoint: Cargar Documento (con almacenamiento local)
@app.post("/documents/upload", response_model=DocumentResponse)
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
    logger.info(f"Intento de carga de documento por usuario: {current_user.email}")
    
    # Validar tipo de archivo
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document", # .docx
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" # .xlsx
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de archivo no permitido. Use PDF, DOCX o XLSX."
        )
    
    # Generar un nombre de archivo único para evitar colisiones
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_location = os.path.join(UPLOAD_DIRECTORY, unique_filename)

    # Guardar el archivo físicamente
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Archivo '{file.filename}' guardado localmente en: {file_location}")
    except Exception as e:
        logger.error(f"Error al guardar el archivo localmente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al guardar el archivo en el servidor."
        )

    # Crear el objeto Documento en la base de datos
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
    
    logger.info(f"Documento '{title}' (ID: {db_document.id}) registrado en la base de datos con ruta: {file_location}.")
    
    return DocumentResponse.from_orm(db_document)

# NUEVO ENDPOINT: Listar Documentos con filtros
@app.get("/documents", response_model=List[DocumentResponse])
def get_documents(
    sector: Optional[str] = Query(None, description="Filtrar por sector"),
    core_line: Optional[str] = Query(None, description="Filtrar por línea medular"),
    document_type: Optional[str] = Query(None, description="Filtrar por tipo de documento"),
    year: Optional[int] = Query(None, description="Filtrar por año"),
    search: Optional[str] = Query(None, description="Buscar en título"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["administrativo", "planeacion", "superadmin"]))
):
    logger.info(f"Solicitud de listado de documentos por usuario: {current_user.email}")
    
    # Construir la consulta base
    query = db.query(Document)
    
    # Aplicar filtros si se proporcionan
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
    
    # Ordenar por fecha de subida (más recientes primero)
    query = query.order_by(Document.uploaded_at.desc())
    
    documents = query.all()
    
    logger.info(f"Se encontraron {len(documents)} documentos con los filtros aplicados.")
    
    return [DocumentResponse.from_orm(doc) for doc in documents]

# NUEVO ENDPOINT: Obtener opciones para filtros (sectores, líneas medulares, tipos)
@app.get("/documents/filter-options")
def get_document_filter_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["administrativo", "planeacion", "superadmin"]))
):
    """
    Obtiene las opciones disponibles para los filtros de documentos
    basándose en los documentos existentes en la base de datos.
    """
    
    # Obtener sectores únicos
    sectors = db.query(Document.sector).distinct().all()
    sectors = [sector[0] for sector in sectors if sector[0]]
    
    # Obtener líneas medulares únicas
    core_lines = db.query(Document.core_line).distinct().all()
    core_lines = [line[0] for line in core_lines if line[0]]
    
    # Obtener tipos de documento únicos
    document_types = db.query(Document.document_type).distinct().all()
    document_types = [doc_type[0] for doc_type in document_types if doc_type[0]]
    
    # Obtener años únicos
    years = db.query(Document.year).distinct().order_by(Document.year.desc()).all()
    years = [year[0] for year in years if year[0]]
    
    return {
        "sectors": sectors,
        "core_lines": core_lines,
        "document_types": document_types,
        "years": years
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)