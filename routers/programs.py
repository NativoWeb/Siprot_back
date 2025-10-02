from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict
import pandas as pd
import io
from datetime import datetime

from models import Program, User, DemandIndicator
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
def bulk_upload_demand_indicators(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    """
    Procesa un archivo CSV o Excel para crear múltiples registros de DemandIndicator.
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
        
        required_columns = ["sector", "year", "demand_value"]
        optional_columns = ["indicator_value", "source_document_id"]
        
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
                # Validar sector
                if pd.isna(row["sector"]) or str(row["sector"]).strip() == "":
                    errors.append(f"Fila {index + 2}: Campo 'sector' es requerido")
                    continue
                
                # Validar año
                if pd.isna(row["year"]):
                    errors.append(f"Fila {index + 2}: Campo 'year' es requerido")
                    continue
                try:
                    year = int(row["year"])
                except ValueError:
                    errors.append(f"Fila {index + 2}: 'year' debe ser un número entero")
                    continue
                
                # Validar demand_value
                if pd.isna(row["demand_value"]):
                    errors.append(f"Fila {index + 2}: Campo 'demand_value' es requerido")
                    continue
                try:
                    demand_value = float(row["demand_value"])
                except ValueError:
                    errors.append(f"Fila {index + 2}: 'demand_value' debe ser numérico")
                    continue

                demand_data = {
                    "sector": str(row["sector"]).strip(),
                    "year": year,
                    "demand_value": demand_value,
                }
                
                if "indicator_value" in df.columns and not pd.isna(row["indicator_value"]):
                    try:
                        demand_data["indicator_value"] = float(row["indicator_value"])
                    except ValueError:
                        errors.append(f"Fila {index + 2}: 'indicator_value' debe ser numérico")
                        continue
                
                if "source_document_id" in df.columns and not pd.isna(row["source_document_id"]):
                    try:
                        demand_data["source_document_id"] = int(row["source_document_id"])
                    except ValueError:
                        errors.append(f"Fila {index + 2}: 'source_document_id' debe ser entero")
                        continue

                # Crear registro
                indicator = DemandIndicator(**demand_data)
                db.add(indicator)
                created_records.append(f"{demand_data['sector']} - {demand_data['year']}")
            
            except Exception as e:
                errors.append(f"Fila {index + 2}: Error procesando datos - {str(e)}")
        
        if created_records:
            db.commit()
        
        return {
            "message": f"Se cargaron {len(created_records)} indicadores. {len(errors)} errores encontrados",
            "created_count": len(created_records),
            "error_count": len(errors),
            "created_indicators": created_records,
            "errors": errors[:10],
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
    year: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(["planeacion", "administrativo", "superadmin"]))
):
    """
    Compara oferta educativa con indicadores de demanda por sector (R3.3).
    """
    try:
        programs_data = (
            db.query(
                Program.sector,
                func.count(Program.id).label("programs"),
                func.sum(Program.current_students).label("current_students")
            )
            .filter(Program.is_active == True)
            .group_by(Program.sector)
            .all()
        )

        try:
            demand_data = (
                db.query(DemandIndicator.sector, DemandIndicator.demand_value)
                .filter(DemandIndicator.year == year)
                .all()
            )
            demand_map = {d.sector: d.demand_value for d in demand_data}
        except Exception as e:
            print(f"Warning: Could not fetch demand indicators: {e}")
            # Return empty demand map if table doesn't exist or has issues
            demand_map = {}

        results = []
        for sector, programs, current_students in programs_data:
            demand_value = demand_map.get(sector, 0)
            results.append({
                "sector": sector,
                "programs": programs,
                "current_students": current_students or 0,
                "demand_value": demand_value,
                "gap": (demand_value - (current_students or 0))
            })

        return results
    
    except Exception as e:
        print(f"Error in demand comparison: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error al obtener comparación de demanda: {str(e)}"
        )


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
