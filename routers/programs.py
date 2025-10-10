from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict
import pandas as pd
import io
from datetime import datetime

from models import Program, User
from schemas import ProgramCreate, ProgramUpdate, ProgramResponse
from routers.auth import get_db, require_role
from dependencies import get_current_user

router = APIRouter(prefix="/programs", tags=["Oferta Educativa"])

# 📄 Obtener todos los programas activos
@router.get("/", response_model=List[ProgramResponse])
def list_programs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo", "superadmin"]))
):
    return (
        db.query(Program)
        .filter(Program.is_active == True)
        .order_by(Program.created_at.desc())
        .all()
    )

# ➕ Crear un nuevo programa
@router.post("/", response_model=ProgramResponse)
def create_program(
    program_data: ProgramCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    # Check if program code already exists
    existing_program = db.query(Program).filter(Program.code == program_data.code).first()
    if existing_program:
        raise HTTPException(status_code=400, detail="El código del programa ya existe")
    
    program = Program(**program_data.dict(), created_by=current_user.id)
    db.add(program)
    db.commit()
    db.refresh(program)
    return program

# 📂 Carga masiva de programas desde CSV/Excel
@router.post("/bulk-upload")
def bulk_upload_programs(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    """
    Procesa un archivo CSV o Excel para crear múltiples programas.
    """
    allowed_types = [
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]
    
    if file.content_type not in allowed_types and not file.filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Formato de archivo no válido. Use CSV o Excel (.csv, .xlsx, .xls)",
        )
    
    try:
        contents = file.file.read()
        
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.StringIO(contents.decode("utf-8")))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        # Columnas requeridas para programas
        required_columns = ["code", "name", "level", "sector", "core_line", "capacity"]
        optional_columns = ["current_students", "region", "description", "program_date"]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Columnas requeridas faltantes: {', '.join(missing_columns)}",
            )
        
        if df.empty:
            raise HTTPException(status_code=400, detail="El archivo está vacío o no contiene datos válidos")
        
        created_records = []
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Validar code
                if pd.isna(row["code"]) or str(row["code"]).strip() == "":
                    errors.append(f"Fila {index + 2}: Campo 'code' es requerido")
                    continue
                
                code = str(row["code"]).strip()
                
                # Verificar si el código ya existe
                existing = db.query(Program).filter(Program.code == code).first()
                if existing:
                    errors.append(f"Fila {index + 2}: El código '{code}' ya existe")
                    continue
                
                # Validar name
                if pd.isna(row["name"]) or str(row["name"]).strip() == "":
                    errors.append(f"Fila {index + 2}: Campo 'name' es requerido")
                    continue
                
                # Validar level
                if pd.isna(row["level"]) or str(row["level"]).strip() == "":
                    errors.append(f"Fila {index + 2}: Campo 'level' es requerido")
                    continue
                
                # Validar sector
                if pd.isna(row["sector"]) or str(row["sector"]).strip() == "":
                    errors.append(f"Fila {index + 2}: Campo 'sector' es requerido")
                    continue
                
                # Validar core_line
                if pd.isna(row["core_line"]) or str(row["core_line"]).strip() == "":
                    errors.append(f"Fila {index + 2}: Campo 'core_line' es requerido")
                    continue
                
                # Validar capacity
                if pd.isna(row["capacity"]):
                    errors.append(f"Fila {index + 2}: Campo 'capacity' es requerido")
                    continue
                try:
                    capacity = int(row["capacity"])
                    if capacity < 0:
                        errors.append(f"Fila {index + 2}: 'capacity' debe ser mayor o igual a 0")
                        continue
                except ValueError:
                    errors.append(f"Fila {index + 2}: 'capacity' debe ser un número entero")
                    continue

                program_data = {
                    "code": code,
                    "name": str(row["name"]).strip(),
                    "level": str(row["level"]).strip(),
                    "sector": str(row["sector"]).strip(),
                    "core_line": str(row["core_line"]).strip(),
                    "capacity": capacity,
                    "created_by": current_user.id
                }
                
                # Campos opcionales
                if "current_students" in df.columns and not pd.isna(row["current_students"]):
                    try:
                        program_data["current_students"] = int(row["current_students"])
                    except ValueError:
                        errors.append(f"Fila {index + 2}: 'current_students' debe ser numérico")
                        continue
                
                if "region" in df.columns and not pd.isna(row["region"]):
                    program_data["region"] = str(row["region"]).strip()
                
                if "description" in df.columns and not pd.isna(row["description"]):
                    program_data["description"] = str(row["description"]).strip()
                
                if "program_date" in df.columns and not pd.isna(row["program_date"]):
                    try:
                        program_data["program_date"] = pd.to_datetime(row["program_date"])
                    except:
                        errors.append(f"Fila {index + 2}: 'program_date' tiene formato inválido")
                        continue
                else:
                    # Si no se proporciona program_date, usar la fecha actual
                    program_data["program_date"] = datetime.utcnow()

                # Crear registro
                program = Program(**program_data)
                db.add(program)
                created_records.append(f"{program_data['code']} - {program_data['name']}")
            
            except Exception as e:
                errors.append(f"Fila {index + 2}: Error procesando datos - {str(e)}")
        
        if created_records:
            db.commit()
        
        return {
            "message": f"Se cargaron {len(created_records)} programas. {len(errors)} errores encontrados",
            "created_count": len(created_records),
            "error_count": len(errors),
            "created_programs": created_records,
            "errors": errors[:10],  # Mostrar solo los primeros 10 errores
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {str(e)}")
    finally:
        file.file.close()

# ✏️ Actualizar un programa existente
@router.put("/{program_id}", response_model=ProgramResponse)
def update_program(
    program_id: int,
    program_data: ProgramUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion"]))
):
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    
    if program_data.code and program_data.code != program.code:
        existing_program = db.query(Program).filter(Program.code == program_data.code).first()
        if existing_program:
            raise HTTPException(status_code=400, detail="El código del programa ya existe")
    
    for field, value in program_data.dict(exclude_unset=True).items():
        setattr(program, field, value)
    
    program.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(program)
    return program

# ❌ Eliminar un programa (soft delete)
@router.delete("/{program_id}")
def delete_program(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion"]))
):
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    
    program.is_active = False
    program.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Programa eliminado exitosamente"}


# ==================== ENDPOINTS DE ANÁLISIS ====================

@router.get("/analysis/matrix")
def analyze_matrix(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["planeacion", "administrativo", "superadmin"]))
) -> Dict[str, Dict[str, int]]:
    """
    Devuelve una matriz sector vs línea medular con conteo de programas (R3.2).
    """
    data = (
        db.query(
            Program.sector,
            Program.core_line,
            func.count(Program.id).label("program_count")
        )
        .filter(Program.is_active == True)
        .group_by(Program.sector, Program.core_line)
        .all()
    )

    result: Dict[str, Dict[str, int]] = {}
    for sector, core_line, count in data:
        if sector not in result:
            result[sector] = {}
        result[sector][core_line] = count

    return result


@router.get("/analysis/demand-comparison")
def analyze_demand_comparison(
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["planeacion", "administrativo", "superadmin"]))
):
    """
    Compara oferta educativa calculando demanda automáticamente por sector (R3.3).
    Fórmula: demanda = (matriculados/cupos) * 100
    """
    programs_data = (
        db.query(
            Program.sector,
            func.count(Program.id).label("programs"),
            func.sum(Program.current_students).label("total_students"),
            func.sum(Program.capacity).label("total_capacity")
        )
        .filter(Program.is_active == True)
        .group_by(Program.sector)
        .all()
    )

    results = []
    for sector, programs, total_students, total_capacity in programs_data:
        total_students = total_students or 0
        total_capacity = total_capacity or 0
        
        # Calcular demanda con la fórmula
        demand_percentage = (total_students / total_capacity * 100) if total_capacity > 0 else 0
        
        results.append({
            "sector": sector,
            "programs": programs,
            "current_students": total_students,
            "total_capacity": total_capacity,
            "demand_percentage": round(demand_percentage, 2),
            "available_spots": total_capacity - total_students
        })

    return results

@router.get("/analysis/filtered", response_model=List[ProgramResponse])
def analyze_filtered(
    sector: Optional[str] = None,

    
    level: Optional[str] = None,
    region: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["planeacion", "administrativo", "superadmin"]))
):
    """
    Devuelve análisis filtrado de oferta educativa (R3.4).
    """
    try:
        query = db.query(Program).filter(Program.is_active == True)

        if sector:
            query = query.filter(Program.sector == sector)
        if level:
            query = query.filter(Program.level == level)
        if region:
            query = query.filter(Program.region == region)

        programs = query.all()
        
        result = []
        for program in programs:
            try:
                # Use from_orm to properly convert the SQLAlchemy model
                program_response = ProgramResponse.from_orm(program)
                result.append(program_response)
            except Exception as validation_error:
                print(f"Validation error for program {program.id}: {validation_error}")
                # Skip invalid programs rather than failing the entire request
                continue
        
        return result
    
    except Exception as e:
        print(f"Error in filtered analysis: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener programas filtrados: {str(e)}"
        )
