from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from routers import auth, users, documents, programs

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

# Incluir routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(programs.router)
