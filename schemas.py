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
    code: str
    name: str
    level: str
    sector: str
    core_line: str
    capacity: int
    current_students: Optional[int] = 0
    region: Optional[str] = None
    description: Optional[str] = None

class ProgramUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    level: Optional[str] = None
    sector: Optional[str] = None
    core_line: Optional[str] = None
    capacity: Optional[int] = None
    current_students: Optional[int] = None
    region: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ProgramResponse(BaseModel):
    id: int
    code: str
    name: str
    level: str
    sector: str
    core_line: str
    capacity: Optional[int]
    current_students: Optional[int]
    region: Optional[str]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    created_by: int

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
    titulo_personalizado: Optional[str] = None  # ← para <h3>{{ reporte.titulo_personalizado }}
    archivo_nombre: Optional[str] = None        # ← para el PDF
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Schemas para Indicadores
class IndicadorCreate(BaseModel):
    nombre: str
    valor_actual: float
    meta: float
    unidad: str
    tendencia: str
    descripcion: Optional[str] = None
    categoria: Optional[str] = None


class IndicadorResponse(IndicadorCreate):
    id: int
    fecha_actualizacion: datetime
    cumplimiento: float
    estado_semaforo: str

    class Config:
        from_attributes = True


class ResumenIndicadores(BaseModel):
    total_indicadores: int
    verde: int
    amarillo: int
    rojo: int
    cumplimiento_general: float

    class Config:
        from_attributes = True

class IndicadorUpdate(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    valor_actual: float
    meta: float
    unidad: str
    categoria: Optional[str] = None
    tendencia: Optional[str] = None


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

# Schemas para escenarios
class ScenarioTypeEnum(str, Enum):
    TENDENCIAL = "tendencial"
    OPTIMISTA = "optimista"
    PESIMISTA = "pesimista"

class ScenarioParametersBase(BaseModel):
    growth_multiplier: float = Field(ge=0.1, le=5.0, description="Multiplicador de crecimiento")
    demand_multiplier: float = Field(ge=0.1, le=5.0, description="Multiplicador de demanda")
    economic_factor: float = Field(ge=0.1, le=3.0, description="Factor económico")
    technology_adoption: float = Field(ge=0.1, le=2.0, description="Adopción tecnológica")

class ScenarioCreate(BaseModel):
    name: str = Field(max_length=100)
    scenario_type: ScenarioTypeEnum
    description: Optional[str] = None
    parameters: ScenarioParametersBase

class ScenarioUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    parameters: Optional[ScenarioParametersBase] = None
    is_active: Optional[bool] = None

class ScenarioResponse(BaseModel):
    id: int
    name: str
    scenario_type: ScenarioTypeEnum
    description: Optional[str]
    parameters: ScenarioParametersBase
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ProjectionRequest(BaseModel):
    scenario_ids: List[int] = Field(description="IDs de escenarios a proyectar")
    sectors: Optional[List[str]] = Field(None, description="Sectores específicos (opcional)")
    years_ahead: int = Field(default=10, ge=1, le=20, description="Años a proyectar")

class ProjectionDataPoint(BaseModel):
    year: int
    sector: str
    indicator_type: str
    base_value: float
    projected_value: float
    multiplier_applied: float

class ScenarioProjectionResponse(BaseModel):
    scenario_id: int
    scenario_name: str
    scenario_type: ScenarioTypeEnum
    projections: List[ProjectionDataPoint]
    summary: Dict[str, Any]

class ScenarioComparisonResponse(BaseModel):
    scenarios: List[ScenarioProjectionResponse]
    comparison_metrics: Dict[str, Any]
    recommendations: List[str]

class ScenarioConfigurationUpdate(BaseModel):
    scenario_type: ScenarioTypeEnum
    parameters: Dict[str, float]

class ScenarioExportRequest(BaseModel):
    scenario_ids: List[int]
    format: str = Field(default="json", pattern="^(json|csv|excel)$")
    include_charts: bool = True
    include_summary: bool = True


# ----------------------- PERMISSIONS ------------------------------------

class PermissionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    resource: str
    action: str

    class Config:
        from_attributes = True

class RolePermissionCreate(BaseModel):
    permission_id: int
    granted: bool

class RolePermissionResponse(BaseModel):
    id: int
    role: str
    permission_id: int
    granted: bool
    created_by: Optional[int] = None

    class Config:
        from_attributes = True

class DofaCategory(str, Enum):
    DEBILIDADES = "D"
    OPORTUNIDADES = "O" 
    FORTALEZAS = "F"
    AMENAZAS = "A"

class DofaPriority(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"

class DofaItemCreate(BaseModel):
    category: DofaCategory = Field(..., description="Categoría DOFA: D, O, F, A")
    text: str = Field(..., min_length=1, max_length=1000, description="Texto del ítem DOFA")
    source: Optional[str] = Field(None, max_length=500, description="Fuente o referencia")
    responsible: Optional[str] = Field(None, max_length=200, description="Responsable")
    priority: Optional[DofaPriority] = Field(None, description="Prioridad del ítem")

class DofaItemUpdate(BaseModel):
    text: Optional[str] = Field(None, min_length=1, max_length=1000)
    source: Optional[str] = Field(None, max_length=500)
    responsible: Optional[str] = Field(None, max_length=200)
    priority: Optional[DofaPriority] = None

class DofaItemResponse(BaseModel):
    id: int
    category: str
    text: str
    source: Optional[str]
    responsible: Optional[str]
    priority: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: int
    updated_by: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True

class DofaMatrixResponse(BaseModel):
    debilidades: List[DofaItemResponse]
    oportunidades: List[DofaItemResponse]
    fortalezas: List[DofaItemResponse]
    amenazas: List[DofaItemResponse]
    total_items: int
    last_updated: Optional[datetime]

class DofaChangeLogResponse(BaseModel):
    id: int
    dofa_item_id: int
    action: str
    changed_at: datetime
    changed_by: int
    details: Optional[str]
    user_email: Optional[str]

    class Config:
        from_attributes = True

class DofaExportRequest(BaseModel):
    format: str = Field(..., pattern="^(pdf|docx)$", description="Formato de exportación: pdf o docx")
    include_metadata: bool = Field(True, description="Incluir metadatos (fechas, responsables)")
    title: Optional[str] = Field("Análisis DOFA", max_length=200, description="Título del documento")

# ==================== AUTH SCHEMAS ====================

class LoginRequest(BaseModel):
    email: str = Field(..., description="Email del usuario")
    password: str = Field(..., description="Contraseña")

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    message: str
    user: UserResponse
    access_token: str
    token_type: str
