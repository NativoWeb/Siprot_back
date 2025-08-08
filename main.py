from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles
import os

from database import engine
from models import Base
from routers import auth, users, documents, programs, reports

# Crear las tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema de Gestión SIPROT", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción cambia esto
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear directorio de reportes si no existe
os.makedirs("uploads/reports", exist_ok=True)

# Montar archivos estáticos para servir los PDFs generados
app.mount("/static/reports", StaticFiles(directory="uploads/reports"), name="reports")

# Incluir routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(programs.router)
app.include_router(reports.router)