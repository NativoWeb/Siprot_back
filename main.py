from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging

# Imports de configuración de base de datos y modelos
from database import engine, SessionLocal
from models import Base

# Imports de todos los routers principales
from routers import auth, users, documents, programs, reports, scenarios, permissions, dofa, indicators, catalogs, projections, demand_indicators
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

Base.metadata.create_all(bind=engine)

# Crear aplicación FastAPI
app = FastAPI(
    title="Sistema de Gestión SIPROT", 
    description="API para gestión de documentos, programas, análisis DOFA y reportes",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev server
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://localhost:8080",  # Vue CLI dev server
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Accept",
        "Accept-Language", 
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers"
    ],
)

UPLOAD_DIRS = [
    "uploads/reports",
    "uploads/docs",
    "uploads/csv"
]

for folder in UPLOAD_DIRS:
    os.makedirs(folder, exist_ok=True)

app.mount("/static/reports", StaticFiles(directory="uploads/reports"), name="reports")

# Incluir routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(programs.router)
app.include_router(reports.router)
app.include_router(scenarios.router)
app.include_router(permissions.router)
app.include_router(dofa.router)
app.include_router(indicators.router)
app.include_router(catalogs.router)
app.include_router(projections.router)
app.include_router(demand_indicators.router)

if AUDIT_AVAILABLE:
    app.include_router(audit_router)
if CATALOGS_AVAILABLE:
    app.include_router(catalogs.router)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Endpoint de salud
@app.get("/")
async def root():
    return {
        "message": "Sistema de Gestión SIPROT - API",
        "version": "1.0.0",
        "status": "active"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
