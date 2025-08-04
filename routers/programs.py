from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from models import Program, User
from schemas import ProgramCreate, ProgramUpdate, ProgramResponse
from routers.auth import get_db, require_role, get_current_user

router = APIRouter(prefix="/programs", tags=["Oferta Educativa"])

# 📄 Obtener todos los programas
@router.get("/", response_model=List[ProgramResponse])
def list_programs(db: Session = Depends(get_db), current_user: User = Depends(require_role(["planeacion", "directivos"]))):
    return db.query(Program).order_by(Program.created_at.desc()).all()

# ➕ Crear un nuevo programa
@router.post("/", response_model=ProgramResponse)
def create_program(program_data: ProgramCreate, db: Session = Depends(get_db), current_user: User = Depends(require_role(["planeacion"]))):
    program = Program(**program_data.dict())
    db.add(program)
    db.commit()
    db.refresh(program)
    return program

# 🔍 Obtener un programa por ID
@router.get("/{program_id}", response_model=ProgramResponse)
def get_program(program_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["planeacion", "directivos"]))):
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    return program

# ✏️ Actualizar un programa existente
@router.put("/{program_id}", response_model=ProgramResponse)
def update_program(program_id: int, program_data: ProgramUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_role(["planeacion"]))):
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programa no encontrado")

    for field, value in program_data.dict(exclude_unset=True).items():
        setattr(program, field, value)

    db.commit()
    db.refresh(program)
    return program

# ❌ Eliminar un programa
@router.delete("/{program_id}")
def delete_program(program_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["planeacion"]))):
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    db.delete(program)
    db.commit()
    return {"message": "Programa eliminado exitosamente"}
