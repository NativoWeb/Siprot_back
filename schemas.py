from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

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


# ----------------------- PDF ------------------------------------

# Enums
class TipoReporte(str, Enum):
    INDICADORES = "indicadores"
    PROSPECTIVA = "prospectiva"
    OFERTA_EDUCATIVA = "oferta_educativa"
    CONSOLIDADO = "consolidado"

class EstadoReporte(str, Enum):
    GENERANDO = "generando"
    COMPLETADO = "completado"
    ERROR = "error"

# Schemas para Reportes
class ParametrosReporte(BaseModel):
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    incluir_graficos: bool = True
    incluir_recomendaciones: bool = True
    comentarios_analista: Optional[str] = None
    indicadores_seleccionados: Optional[List[str]] = None

class SolicitudReporte(BaseModel):
    tipo: TipoReporte
    parametros: ParametrosReporte
    # ← Quitar usuario_id del request, se toma del usuario autenticado

class ReporteResponse(BaseModel):
    id: int
    tipo: TipoReporte
    fecha_generacion: datetime
    usuario_id: int
    parametros: ParametrosReporte
    estado: EstadoReporte
    archivo_path: Optional[str] = None
    tamaño_archivo: Optional[int] = None
    
    class Config:
        from_attributes = True

# Schemas para Indicadores
class IndicadorBase(BaseModel):
    id: str
    nombre: str
    valor_actual: float
    meta: float
    unidad: str
    tendencia: str
    descripcion: Optional[str] = None
    categoria: Optional[str] = None

class IndicadorResponse(IndicadorBase):
    fecha_actualizacion: datetime
    cumplimiento: float
    estado_semaforo: str
    
    class Config:
        from_attributes = True

class TipoReporteInfo(BaseModel):
    tipo: TipoReporte
    nombre: str
    descripcion: str
    tiempo_estimado: str
    opciones_disponibles: List[str]

# Schemas adicionales para datos específicos
class ResumenIndicadores(BaseModel):
    total_indicadores: int
    verde: int
    amarillo: int
    rojo: int
    cumplimiento_general: float

class EscenarioProspectiva(BaseModel):
    nombre: str
    descripcion: str
    probabilidad: int
    impacto: str
    recomendaciones: List[str]

class TendenciaSectorial(BaseModel):
    sector: str
    crecimiento_esperado: float
    demanda: str

class ProgramaSector(BaseModel):
    sector: str
    programas_activos: int
    cupos: int
    ocupacion: int

class BrechaFormativa(BaseModel):
    area: str
    demanda: int
    oferta: int
    brecha: int

class ResumenEjecutivo(BaseModel):
    fortalezas: List[str]
    oportunidades: List[str]
    debilidades: List[str]
    amenazas: List[str]

# Schemas para respuestas de progreso
class ProgresoReporte(BaseModel):
    id: int
    estado: EstadoReporte
    fecha_generacion: datetime
    archivo_disponible: bool
    porcentaje_completado: Optional[int] = None
    mensaje_estado: Optional[str] = None

# Schema para estadísticas de reportes
class EstadisticasReportes(BaseModel):
    total_reportes: int
    reportes_completados: int
    reportes_en_proceso: int
    reportes_con_error: int
    reportes_por_tipo: Dict[str, int]
    tiempo_promedio_generacion: Optional[float] = None