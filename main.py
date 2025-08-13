from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from database import engine, SessionLocal
from models import Base

# Routers principales
from routers import auth, users, documents, programs, reports, scenarios
# Auditoría
try:
    from routers.audit import router as audit_router
    AUDIT_AVAILABLE = True
except ImportError:
    print("Warning: Audit module not found. Audit functionality will be disabled.")
    AUDIT_AVAILABLE = False

# Catálogos
try:
    from routers import catalogs
    from routers.catalogs import initialize_default_catalogs
    CATALOGS_AVAILABLE = True
except ImportError:
    print("Warning: Catalogs module not found.")
    CATALOGS_AVAILABLE = False

# Configuración global (si está disponible)
try:
    from routers.system_config import initialize_default_configs
    CONFIG_AVAILABLE = True
except ImportError:
    print("Warning: System config module not found.")
    CONFIG_AVAILABLE = False

# Crear las tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sistema de Gestión SIPROT", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ Cambiar en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directorios necesarios
UPLOAD_DIRS = [
    "uploads/reports",
    "uploads/docs",
    "uploads/csv"
]

for folder in UPLOAD_DIRS:
    os.makedirs(folder, exist_ok=True)

# Montar archivos estáticos
app.mount("/static/reports", StaticFiles(directory="uploads/reports"), name="reports")

# Incluir routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(programs.router)
app.include_router(reports.router)
app.include_router(scenarios.router)

if AUDIT_AVAILABLE:
    app.include_router(audit_router)
if CATALOGS_AVAILABLE:
    app.include_router(catalogs.router)

# ==================== EVENTO DE INICIO ====================

@app.on_event("startup")
def startup_event():
    db = SessionLocal()

    # Inicializar catálogos si está disponible
    if CATALOGS_AVAILABLE:
        initialize_default_catalogs(db, created_by=1)
        print("✅ Catálogos maestros inicializados.")

    # Inicializar configuraciones globales si está disponible
    if CONFIG_AVAILABLE:
        initialize_default_configs(db, created_by=1)
        print("✅ Configuración global inicializada.")

    db.close()
    print("🚀 Sistema de Gestión SIPROT iniciado correctamente.")



