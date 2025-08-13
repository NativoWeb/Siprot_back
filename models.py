from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, func, ForeignKey, LargeBinary, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from database import Base
import enum
from datetime import datetime


class UserRole(enum.Enum):
    SUPERADMIN = "superadmin"
    ADMINISTRATIVO = "administrativo"
    PLANEACION = "planeacion"
    INSTRUCTOR = "instructor"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False) # Email es ahora el identificador único
    password = Column(String(255), nullable=False)
    
    first_name = Column(String(100), nullable=True) # Nombre
    last_name = Column(String(100), nullable=True)  # Apellido
    phone_number = Column(String(20), nullable=True) # Teléfono
    additional_notes = Column(String(500), nullable=True) # Notas adicionales (descripción leve)
    
    role = Column(String(20), nullable=False, default="instructor")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relación con los documentos subidos por este usuario
    uploaded_documents = relationship("Document", back_populates="uploader")

    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role}')>"

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)  # Add this
    file_extension = Column(String(10), nullable=False)     # Add this
    mime_type = Column(String(100), nullable=False)   
    year = Column(Integer, nullable=False)
    sector = Column(String(100), nullable=False)
    core_line = Column(String(100), nullable=False)
    document_type = Column(String(100), nullable=False)
    additional_notes = Column(String(500), nullable=True)
    file_path = Column(String(500), nullable=False) # Ruta donde se gu
    
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relación con el usuario que subió el documento
    uploader = relationship("User", back_populates="uploaded_documents")

    def __repr__(self):
        return f"<Document(title='{self.title}', type='{self.document_type}')>"

class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    level = Column(String, nullable=False)  # tecnólogo, especialización, etc.
    sector = Column(String, nullable=False)
    core_line = Column(String, nullable=False)
    quota = Column(Integer)  # cupos o aprendices
    region = Column(String)  # para R3.4
    created_at = Column(DateTime, default=datetime.utcnow)

class DemandIndicator(Base):
    __tablename__ = "demand_indicators"

    id = Column(Integer, primary_key=True)
    sector = Column(String, nullable=False)
    indicator_value = Column(Float)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)  # relación con biblioteca

class ProjectionSetting(Base):
    __tablename__ = "projection_settings"

    id = Column(Integer, primary_key=True)
    sector = Column(String)
    growth_rate = Column(Float)  # % anual
    years_to_project = Column(Integer, default=10)

# ----------------------- PDF ------------------------------------

class Reporte(Base):
    __tablename__ = "reportes"
    
    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(50), nullable=False)  # indicadores, prospectiva, etc.
    estado = Column(String(20), default="generando")
    fecha_generacion = Column(DateTime, default=datetime.utcnow)
    usuario_id = Column(Integer, nullable=False)
    parametros = Column(JSON)  # Almacenar parámetros como JSON
    archivo_path = Column(String(255))
    tamaño_archivo = Column(Integer)
    tiempo_generacion = Column(Integer)  # En segundos
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Campos adicionales para metadata
    titulo_personalizado = Column(String(200))
    tags = Column(JSON)  # Para categorización
    version = Column(String(10), default="1.0")
    compartido = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<Reporte(id={self.id}, tipo='{self.tipo}', estado='{self.estado}')>"

class Indicador(Base):
    __tablename__ = "indicadores"
    
    id = Column(String(100), primary_key=True)
    nombre = Column(String(200), nullable=False)
    valor_actual = Column(Float, nullable=False)
    meta = Column(Float, nullable=False)
    unidad = Column(String(50), nullable=False)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow)
    tendencia = Column(String(20))  # positiva, negativa, estable
    descripcion = Column(Text)
    categoria = Column(String(100))
    fuente_datos = Column(String(200))
    responsable = Column(String(100))
    frecuencia_actualizacion = Column(String(50))  # diaria, semanal, mensual, etc.
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Campos para historial
    valores_historicos = Column(JSON)  # Array de {fecha, valor}
    metas_historicas = Column(JSON)   # Array de {fecha, meta}
    
    def __repr__(self):
        return f"<Indicador(id='{self.id}', nombre='{self.nombre}', valor={self.valor_actual})>"

# Tabla adicional para logging de generación de reportes
class LogReporte(Base):
    __tablename__ = "logs_reportes"
    
    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    nivel = Column(String(20))  # INFO, WARNING, ERROR
    mensaje = Column(Text)
    detalle = Column(JSON)  # Información adicional en formato JSON
    duracion = Column(Float)  # Duración de la operación en segundos
    
    def __repr__(self):
        return f"<LogReporte(reporte_id={self.reporte_id}, nivel='{self.nivel}')>"

# Tabla para configuraciones de reportes
class ConfiguracionReporte(Base):
    __tablename__ = "configuraciones_reportes"
    
    id = Column(Integer, primary_key=True, index=True)
    tipo_reporte = Column(String(50), nullable=False)
    nombre_configuracion = Column(String(100), nullable=False)
    parametros_default = Column(JSON)
    plantilla_personalizada = Column(Text)  # HTML/CSS personalizado
    usuario_id = Column(Integer)  # Si es configuración personal
    publica = Column(Boolean, default=False)
    activa = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ConfiguracionReporte(tipo='{self.tipo_reporte}', nombre='{self.nombre_configuracion}')>"
    
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_email = Column(String, nullable=True)
    target_type = Column(String, nullable=True)
    target_id = Column(String, nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(50), nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    details = Column(JSON, nullable=True)  # CAMBIADO: de Text a JSON
    
    # Relación con usuario
    user = relationship("User")
    
    def __repr__(self):
        return f"<AuditLog(action='{self.action}', resource='{self.resource_type}:{self.resource_id}')>"

class Sector(Base):
    __tablename__ = "sectors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    creator = relationship("User")
    
    def __repr__(self):
        return f"<Sector(name='{self.name}')>"

class CoreLine(Base):
    __tablename__ = "core_lines"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=True)  # Opcional: asociar a sector
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    sector = relationship("Sector")
    creator = relationship("User")
    
    def __repr__(self):
        return f"<CoreLine(name='{self.name}')>"

class DocumentType(Base):
    __tablename__ = "document_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    allowed_extensions = Column(JSON, nullable=True)  # ["pdf", "docx", "xlsx"]
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    creator = relationship("User")
    
    def __repr__(self):
        return f"<DocumentType(name='{self.name}')>"

class SystemConfiguration(Base):
    __tablename__ = "system_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=True)
    data_type = Column(String(20), default="string")  # string, integer, boolean, json
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # ui, email, security, etc.
    is_public = Column(Boolean, default=False)  # Si puede ser accedido sin autenticación
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    updater = relationship("User")
    
    def __repr__(self):
        return f"<SystemConfiguration(key='{self.key}')>"

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User")
    
    def __repr__(self):
        return f"<PasswordResetToken(user_id={self.user_id}, used={self.used})>"

class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    resource = Column(String(50), nullable=False)  # users, documents, reports, etc.
    action = Column(String(50), nullable=False)    # create, read, update, delete, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Permission(name='{self.name}')>"

class RolePermission(Base):
    __tablename__ = "role_permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(20), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    granted = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    permission = relationship("Permission")
    creator = relationship("User")
    
    def __repr__(self):
        return f"<RolePermission(role='{self.role}', permission_id={self.permission_id})>"
    
class ScenarioType(enum.Enum):
    TENDENCIAL = "tendencial"
    OPTIMISTA = "optimista"
    PESIMISTA = "pesimista"

class Scenario(Base):
    __tablename__ = "scenarios"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    scenario_type = Column(String(20), nullable=False)  # tendencial, optimista, pesimista
    description = Column(Text, nullable=True)
    parameters = Column(JSON, nullable=False)  # Multiplicadores y configuraciones
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    creator = relationship("User")
    
    def __repr__(self):
        return f"<Scenario(name='{self.name}', type='{self.scenario_type}')>"

class ScenarioProjection(Base):
    __tablename__ = "scenario_projections"
    
    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False)
    sector = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False)
    projected_value = Column(Float, nullable=False)
    base_value = Column(Float, nullable=False)  # Valor base del modelo LSTM
    multiplier_applied = Column(Float, nullable=False)
    indicator_type = Column(String(50), nullable=False)  # demanda, oferta, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    scenario = relationship("Scenario")
    
    def __repr__(self):
        return f"<ScenarioProjection(scenario_id={self.scenario_id}, year={self.year})>"

class ScenarioConfiguration(Base):
    __tablename__ = "scenario_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    scenario_type = Column(String(20), nullable=False)
    parameter_name = Column(String(100), nullable=False)
    parameter_value = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    updater = relationship("User")
    
    def __repr__(self):
        return f"<ScenarioConfiguration(type='{self.scenario_type}', param='{self.parameter_name}')>"

