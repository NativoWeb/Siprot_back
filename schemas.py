from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# ==================== USERS ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    additional_notes: Optional[str] = None
    role: str = "instructor"

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    additional_notes: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

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

class LoginRequest(BaseModel):
    email: str = Field(..., description="Email del usuario")
    password: str = Field(..., description="Contraseña")

class LoginResponse(BaseModel):
    message: str
    user: UserResponse
    access_token: str
    token_type: str

# ==================== DOCUMENTS ====================

class DocumentCreate(BaseModel):
    title: str
    year: int
    sector: str
    core_line: str
    document_type: str
    additional_notes: Optional[str] = None

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
    file_size: int  # <-- agregar este campo


    class Config:
        from_attributes = True

# ==================== PROGRAMS ====================

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
    program_date: datetime  # 

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
    program_date: Optional[datetime] = None 
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
    program_date: datetime   
    created_at: datetime
    updated_at: datetime
    created_by: int

    class Config:
        from_attributes = True


# ==================== REPORTS ====================

class TipoReporte(str, Enum):
    INDICADORES = "indicadores"
    PROSPECTIVA = "prospectiva"
    OFERTA_EDUCATIVA = "oferta_educativa"
    CONSOLIDADO = "consolidado"

class EstadoReporte(str, Enum):
    GENERANDO = "generando"
    COMPLETADO = "completado"
    ERROR = "error"

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

class ReporteResponse(BaseModel):
    id: int
    tipo: TipoReporte
    fecha_generacion: datetime
    usuario_id: int
    parametros: ParametrosReporte
    estado: EstadoReporte
    archivo_path: Optional[str] = None
    tamaño_archivo: Optional[int] = None
    titulo_personalizado: Optional[str] = None
    archivo_nombre: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TipoReporteInfo(BaseModel):
    tipo: TipoReporte
    nombre: str
    descripcion: str
    tiempo_estimado: str
    opciones_disponibles: List[str]

class ProgresoReporte(BaseModel):
    id: int
    estado: EstadoReporte
    fecha_generacion: datetime
    archivo_disponible: bool
    porcentaje_completado: Optional[int] = None
    mensaje_estado: Optional[str] = None

class EstadisticasReportes(BaseModel):
    total_reportes: int
    reportes_completados: int
    reportes_en_proceso: int
    reportes_con_error: int
    reportes_por_tipo: Dict[str, int]
    tiempo_promedio_generacion: Optional[float] = None

# ==================== INDICATORS ====================

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

class IndicadorUpdate(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    valor_actual: float
    meta: float
    unidad: str
    categoria: Optional[str] = None
    tendencia: Optional[str] = None

class ResumenIndicadores(BaseModel):
    total_indicadores: int
    verde: int
    amarillo: int
    rojo: int
    cumplimiento_general: float

# ==================== SCENARIOS ====================

class ScenarioTypeEnum(str, Enum):
    TENDENCIAL = "tendencial"
    OPTIMISTA = "optimista"
    PESIMISTA = "pesimista"

class ScenarioParametersBase(BaseModel):
    growth_multiplier: float = Field(ge=0.1, le=5.0)
    demand_multiplier: float = Field(ge=0.1, le=5.0)
    economic_factor: float = Field(ge=0.1, le=3.0)
    technology_adoption: float = Field(ge=0.1, le=2.0)

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
    scenario_ids: List[int]
    sectors: Optional[List[str]] = None
    years_ahead: int = Field(default=10, ge=1, le=20)

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

# ==================== PERMISSIONS ====================

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

# ==================== DOFA ====================

class DofaCategory(str, Enum):
    DEBILIDADES = "D"
    OPORTUNIDADES = "O"
    FORTALEZAS = "F"
    AMENAZAS = "A"

class DofaPriority(str, Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baixa"

class DofaItemCreate(BaseModel):
    category: DofaCategory
    text: str
    source: Optional[str] = None
    responsible: Optional[str] = None
    priority: Optional[DofaPriority] = None

class DofaItemUpdate(BaseModel):
    text: Optional[str] = None
    source: Optional[str] = None
    responsible: Optional[str] = None
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
    format: str = Field(..., pattern="^(pdf|docx)$")
    include_metadata: bool = Field(True)
    title: Optional[str] = "Análisis DOFA"

# ==================== SECTORES ====================

class SectorCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: Optional[bool] = True

class SectorUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class SectorResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    created_by: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ==================== CORE LINES ====================

class CoreLineCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sector_id: Optional[int] = None
    is_active: Optional[bool] = True
    created_by: int

class CoreLineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sector_id: Optional[int] = None
    is_active: Optional[bool] = None

class CoreLineResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    sector_id: Optional[int]
    is_active: bool
    created_by: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ==================== DOCUMENT TYPES ====================

class DocumentTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    allowed_extensions: Optional[list[str]] = None
    is_active: Optional[bool] = True
    created_by: int

class DocumentTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    allowed_extensions: Optional[list[str]] = None
    is_active: Optional[bool] = None

class DocumentTypeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    allowed_extensions: Optional[list[str]]
    is_active: bool
    created_by: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True