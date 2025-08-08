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