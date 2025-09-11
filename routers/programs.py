from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import io
from datetime import datetime

from models import Program, User
from schemas import ProgramCreate, ProgramUpdate, ProgramResponse
from routers.auth import get_db, require_role, get_current_user

router = APIRouter(prefix="/programs", tags=["Oferta Educativa"])

# 📄 Obtener todos los programas activos
@router.get("/", response_model=List[ProgramResponse])
def list_programs(db: Session = Depends(get_db), current_user: User = Depends(require_role(["planeacion", "administrativo", "superadmin"]))):
    return db.query(Program).filter(Program.is_active == True).order_by(Program.created_at.desc()).all()

# ➕ Crear un nuevo programa
@router.post("/", response_model=ProgramResponse)
def create_program(program_data: ProgramCreate, db: Session = Depends(get_db), current_user: User = Depends(require_role(["planeacion", "superadmin"]))):
    # Check if program code already exists
    existing_program = db.query(Program).filter(Program.code == program_data.code).first()
    if existing_program:
        raise HTTPException(status_code=400, detail="El código del programa ya existe")
    
    program = Program(**program_data.dict(), created_by=current_user.id)
    db.add(program)
    db.commit()
    db.refresh(program)
    return program

@router.post("/bulk-upload")
def bulk_upload_programs(
    file: UploadFile = File(...),
    
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    """



    Procesa un archivo CSV o Excel para crear múltiples programas.
    Valida el formato y las columnas requeridas antes de guardar.
    """
    
    # Validar tipo de archivo
    allowed_types = [
        'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ]
    
    if file.content_type not in allowed_types and not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(
            status_code=400,
            detail="Formato de archivo no válido. Use CSV o Excel (.csv, .xlsx, .xls)"
        )
    
    try:
        # Leer el archivo
        contents = file.file.read()
        
        # Procesar según el tipo de archivo
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        else:
            df = pd.read_excel(io.BytesIO(contents))
        
        # Validar columnas requeridas
        required_columns = ['code', 'name', 'sector', 'level', 'core_line']
        optional_columns = ['capacity', 'region', 'description', 'current_students']
        all_expected_columns = required_columns + optional_columns
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Columnas requeridas faltantes: {', '.join(missing_columns)}"
            )
        
        # Validar que no esté vacío
        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="El archivo está vacío o no contiene datos válidos"
            )
        
        # Procesar cada fila
        created_programs = []
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Validar campos requeridos
                for col in required_columns:
                    if pd.isna(row[col]) or str(row[col]).strip() == '':
                        errors.append(f"Fila {index + 2}: Campo '{col}' es requerido")
                        continue
                
                # Verificar si el código ya existe
                existing_program = db.query(Program).filter(Program.code == str(row['code']).strip()).first()
                if existing_program:
                    errors.append(f"Fila {index + 2}: El código '{row['code']}' ya existe")
                    continue
                
                # Preparar datos del programa
                program_data = {
                    'code': str(row['code']).strip(),
                    'name': str(row['name']).strip(),
                    'sector': str(row['sector']).strip(),
                    'level': str(row['level']).strip(),
                    'core_line': str(row['core_line']).strip(),
                    'created_by': current_user.id
                }
                
                # Agregar campos opcionales si están presentes
                if 'capacity' in df.columns and not pd.isna(row['capacity']):
                    try:
                        program_data['capacity'] = int(row['capacity'])
                    except (ValueError, TypeError):
                        errors.append(f"Fila {index + 2}: 'capacity' debe ser un número entero")
                        continue
                
                if 'current_students' in df.columns and not pd.isna(row['current_students']):
                    try:
                        program_data['current_students'] = int(row['current_students'])
                    except (ValueError, TypeError):
                        errors.append(f"Fila {index + 2}: 'current_students' debe ser un número entero")
                        continue
                
                if 'region' in df.columns and not pd.isna(row['region']):
                    program_data['region'] = str(row['region']).strip()
                
                if 'description' in df.columns and not pd.isna(row['description']):
                    program_data['description'] = str(row['description']).strip()
                
                # Crear el programa
                program = Program(**program_data)
                db.add(program)
                created_programs.append(program_data['code'])
                
            except Exception as e:
                errors.append(f"Fila {index + 2}: Error procesando datos - {str(e)}")
        
        # Confirmar cambios si hay programas creados
        if created_programs:
            db.commit()
        
        # Preparar respuesta
        if created_programs and not errors:
            message = f"✅ Se crearon {len(created_programs)} programas exitosamente"
        elif created_programs and errors:
            message = f"⚠️ Se crearon {len(created_programs)} programas. {len(errors)} filas tuvieron errores"
        else:
            message = f"❌ No se pudo crear ningún programa. {len(errors)} errores encontrados"
        
        return {
            "message": message,
            "created_count": len(created_programs),
            "error_count": len(errors),
            "created_programs": created_programs,
            "errors": errors[:10]  # Limitar a 10 errores para no sobrecargar la respuesta
        }
        
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    except pd.errors.ParserError:
        raise HTTPException(status_code=400, detail="Error al leer el archivo. Verifique el formato")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {str(e)}")
    finally:
        file.file.close()

# ✏️ Actualizar un programa existente
@router.put("/{program_id}", response_model=ProgramResponse)
def update_program(program_id: int, program_data: ProgramUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_role(["planeacion"]))):
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programa no encontrado")

    # Check if new code already exists (if being updated)
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
def delete_program(program_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_role(["planeacion"]))):
    program = db.query(Program).filter(Program.id == program_id).first()
    if not program:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    
    program.is_active = False
    program.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Programa eliminado exitosamente"}
