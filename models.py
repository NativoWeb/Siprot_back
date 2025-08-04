from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, ForeignKey, LargeBinary, JSON
from sqlalchemy.orm import relationship
from database import Base
import enum

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
    content = Column(LargeBinary, nullable=False)
    prediction = Column(JSON, nullable=True)
    title = Column(String(255), nullable=False)
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
