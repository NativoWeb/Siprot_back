from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class LoginRequest(BaseModel):
    email: EmailStr # Login ahora solo con email
    password: str # <--- ESTE CAMPO ES CRUCIAL

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    additional_notes: Optional[str] = None
    role: str = "instructor"

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    additional_notes: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    message: str
    user: UserResponse
    access_token: str
    token_type: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    additional_notes: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None  # ✅ Añadido

# Nuevo esquema para la creación de documentos
class DocumentCreate(BaseModel):
    title: str
    year: int
    sector: str
    core_line: str
    document_type: str
    additional_notes: Optional[str] = None
    # file_path no se incluye aquí porque se generará en el backend

# Nuevo esquema para la respuesta de documentos
class DocumentResponse(BaseModel):
    id: int
    title: str
    original_filename: str       
    file_extension: str          
    mime_type: str     
    year: int
    sector: str
    core_line: str
    document_type: str
    additional_notes: Optional[str] = None
    file_path: str
    uploaded_by_user_id: int
    uploaded_at: datetime

    class Config:
        from_attributes = True

class ProgramCreate(BaseModel):
    name: str
    level: str
    sector: str
    core_line: str
    quota: Optional[int] = None
    region: Optional[str] = None

class ProgramUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[str] = None
    sector: Optional[str] = None
    core_line: Optional[str] = None
    quota: Optional[int] = None
    region: Optional[str] = None

class ProgramResponse(BaseModel):
    id: int
    name: str
    level: str
    sector: str
    core_line: str
    quota: Optional[int]
    region: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True