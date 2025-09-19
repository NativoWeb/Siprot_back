from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict
from models import Document, User, Scenario
from routers.auth import get_db, require_role
from scenario_engine import ScenarioEngine, ScenarioType
from dependencies import get_current_user
import pandas as pd
import os
import logging
import chardet

router = APIRouter(prefix="/scenarios", tags=["Escenarios"])
logger = logging.getLogger(__name__)

def read_flexible_file(file_path: str, extension: str) -> pd.DataFrame:
    if extension == ".csv":
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
        separators = [";", ",", "\t", "|"]
        df = None

        # 🔹 Detectar encoding primero con chardet
        with open(file_path, "rb") as f:
            result = chardet.detect(f.read(100000))
        detected_encoding = result["encoding"] or "utf-8"

        for sep in separators:
            try:
                df = pd.read_csv(file_path, encoding=detected_encoding, sep=sep)
                # Validar: si tiene más de 1 columna, entonces el separador es correcto
                if df.shape[1] > 1:
                    print(f"✅ CSV leído con encoding={detected_encoding}, sep='{sep}'")
                    break
            except Exception:
                continue
    else:
        df = pd.read_excel(file_path)

    if df is None or df.empty or df.shape[1] == 1:
        raise ValueError("No se pudo leer el archivo correctamente (verifique el separador y formato)")

    # Limpieza de columnas
    df.columns = df.columns.str.strip()

    # Normalizar texto en columnas de tipo object
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="ignore")

    return df

@router.get("/csv-files", response_model=List[Dict])
def get_csv_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo", "instructor"]))
):
    """Obtiene la lista de archivos CSV/XLSX disponibles"""
    try:
        csv_documents = db.query(Document).filter(
            Document.file_extension.in_(['.csv', '.xlsx'])
        ).order_by(Document.uploaded_at.desc()).all()

        return [
            {
                "id": doc.id,
                "title": doc.title,
                "original_filename": doc.original_filename,
                "year": doc.year,
                "sector": doc.sector,
                "core_line": doc.core_line,
                "document_type": doc.document_type,
                "file_extension": doc.file_extension,
                "uploaded_at": doc.uploaded_at.isoformat()
            }
            for doc in csv_documents
        ]
    except Exception as e:
        logger.error(f"Error obteniendo archivos CSV: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener archivos CSV"
        )

@router.post("/generate/{document_id}")
def generate_scenarios_from_csv(
    document_id: int,
    scenario_types: List[str] = ["tendencial", "optimista", "pesimista"],
    years_ahead: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo"]))
):
    """Genera escenarios prospectivos basados en un archivo CSV/XLSX"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

        if document.file_extension not in ['.csv', '.xlsx']:
            raise HTTPException(status_code=400, detail="El archivo debe ser CSV o XLSX")

        file_path = os.path.abspath(document.file_path)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")

        try:
            df = read_flexible_file(file_path, document.file_extension)
        except Exception as e:
            logger.error(f"Error leyendo archivo {file_path}: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Error al leer el archivo: {str(e)}. Verifique que el archivo tenga el formato correcto."
            )

        engine = ScenarioEngine(db)
        scenarios_data = {}

        for scenario_type in scenario_types:
            try:
                scenario_enum = ScenarioType(scenario_type)

                # Buscar escenario existente
                existing_scenario = db.query(Scenario).filter(
                    Scenario.scenario_type == scenario_type,
                    Scenario.name.like(f"%{document.title}%")
                ).first()

                if not existing_scenario:
                    scenario_data = {
                        "name": f"{engine.scenarios[scenario_enum].name} - {document.title}",
                        "scenario_type": scenario_type,
                        "description": f"{engine.scenarios[scenario_enum].description} Basado en: {document.title}",
                        "parameters": {
                            "source_document_id": document_id,
                            "multipliers": engine.scenarios[scenario_enum].multipliers,
                            "growth_rates": engine.scenarios[scenario_enum].growth_rates
                        }
                    }
                    scenario = engine.create_scenario(scenario_data, current_user.id)
                else:
                    scenario = existing_scenario

                # Generar proyecciones
                projections = engine.generate_scenario_projections(scenario.id, df, years_ahead)

                scenarios_data[scenario_type] = {
                    "scenario_type": scenario_type,
                    "scenario_name": scenario.name,
                    "description": scenario.description,
                    "color": get_scenario_color(scenario_type),
                    "data": projections,
                    "parameters": scenario.parameters,
                    "source_document": {
                        "id": document.id,
                        "title": document.title,
                        "filename": document.original_filename
                    },
                    "metadata": {
                        "total_years": len(projections),
                        "historical_years": len([p for p in projections if p['year'] <= pd.Timestamp.now().year]),
                        "future_years": len([p for p in projections if p['year'] > pd.Timestamp.now().year]),
                        "indicators": list(projections[0]['values'].keys()) if projections else []
                    }
                }

                logger.info(f"Escenario {scenario_type} generado con {len(projections)} puntos")
            except Exception as e:
                logger.error(f"Error generando escenario {scenario_type}: {str(e)}")
                continue

        if not scenarios_data:
            raise HTTPException(status_code=500, detail="No se pudieron generar escenarios")

        logger.info(f"Escenarios generados exitosamente para documento {document_id}")
        return scenarios_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/compare")
def compare_scenarios(
    scenario_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo", "instructor"]))
):
    """Compara múltiples escenarios lado a lado"""
    try:
        scenarios = db.query(Scenario).filter(Scenario.id.in_(scenario_ids)).all()
        if len(scenarios) != len(scenario_ids):
            raise HTTPException(status_code=404, detail="Algunos escenarios no fueron encontrados")

        engine = ScenarioEngine(db)
        comparison_data = []
        for scenario in scenarios:
            comparison_data.append({
                "scenario_id": scenario.id,
                "scenario_name": scenario.name,
                "scenario_type": scenario.scenario_type,
                "color": get_scenario_color(scenario.scenario_type),
                "parameters": scenario.parameters
            })

        return {
            "scenarios": comparison_data,
            "comparison_metadata": {
                "total_scenarios": len(scenarios),
                "scenario_types": list(set(s.scenario_type for s in scenarios))
            }
        }
    except Exception as e:
        logger.error(f"Error comparando escenarios: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al comparar escenarios")

@router.get("/list", response_model=List[Dict])
def list_existing_scenarios(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo", "instructor"]))
):
    """Lista todos los escenarios existentes para visualización por instructores"""
    try:
        scenarios = db.query(Scenario).filter(
            Scenario.is_active == True
        ).order_by(Scenario.created_at.desc()).all()

        scenarios_list = []
        for scenario in scenarios:
            # Get creator information
            creator = db.query(User).filter(User.id == scenario.created_by).first()
            
            # Get source document if available
            source_document = None
            if scenario.parameters and 'source_document_id' in scenario.parameters:
                doc_id = scenario.parameters['source_document_id']
                source_document = db.query(Document).filter(Document.id == doc_id).first()
            
            scenario_data = {
                "id": scenario.id,
                "name": scenario.name,
                "scenario_type": scenario.scenario_type,
                "description": scenario.description,
                "parameters": scenario.parameters,
                "created_at": scenario.created_at.isoformat(),
                "created_by": {
                    "id": creator.id if creator else None,
                    "email": creator.email if creator else "Usuario eliminado",
                    "role": creator.role if creator else None,
                    "full_name": f"{creator.first_name} {creator.last_name}".strip() if creator and creator.first_name else creator.email if creator else "Usuario eliminado"
                },
                "source_document": {
                    "id": source_document.id if source_document else None,
                    "title": source_document.title if source_document else None,
                    "filename": source_document.original_filename if source_document else None,
                    "year": source_document.year if source_document else None,
                    "sector": source_document.sector if source_document else None
                } if source_document else None,
                "color": get_scenario_color(scenario.scenario_type)
            }
            scenarios_list.append(scenario_data)

        return scenarios_list

    except Exception as e:
        logger.error(f"Error listando escenarios: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener la lista de escenarios"
        )

@router.get("/details/{scenario_id}")
def get_scenario_details(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo", "instructor"]))
):
    """Obtiene los detalles completos de un escenario específico incluyendo proyecciones"""
    try:
        scenario = db.query(Scenario).filter(
            Scenario.id == scenario_id,
            Scenario.is_active == True
        ).first()
        
        if not scenario:
            raise HTTPException(status_code=404, detail="Escenario no encontrado")

        # Get creator information
        creator = db.query(User).filter(User.id == scenario.created_by).first()
        
        # Get source document if available
        source_document = None
        if scenario.parameters and 'source_document_id' in scenario.parameters:
            doc_id = scenario.parameters['source_document_id']
            source_document = db.query(Document).filter(Document.id == doc_id).first()
            
            # If we have a source document, regenerate projections
            if source_document:
                try:
                    file_path = os.path.abspath(source_document.file_path)
                    if os.path.exists(file_path):
                        df = read_flexible_file(file_path, source_document.file_extension)
                        engine = ScenarioEngine(db)
                        projections = engine.generate_scenario_projections(scenario.id, df, 10)
                    else:
                        projections = []
                except Exception as e:
                    logger.warning(f"No se pudieron regenerar proyecciones para escenario {scenario_id}: {str(e)}")
                    projections = []
            else:
                projections = []
        else:
            projections = []

        scenario_details = {
            "id": scenario.id,
            "name": scenario.name,
            "scenario_type": scenario.scenario_type,
            "description": scenario.description,
            "parameters": scenario.parameters,
            "created_at": scenario.created_at.isoformat(),
            "updated_at": scenario.updated_at.isoformat(),
            "created_by": {
                "id": creator.id if creator else None,
                "email": creator.email if creator else "Usuario eliminado",
                "role": creator.role if creator else None,
                "full_name": f"{creator.first_name} {creator.last_name}".strip() if creator and creator.first_name else creator.email if creator else "Usuario eliminado"
            },
            "source_document": {
                "id": source_document.id if source_document else None,
                "title": source_document.title if source_document else None,
                "filename": source_document.original_filename if source_document else None,
                "year": source_document.year if source_document else None,
                "sector": source_document.sector if source_document else None,
                "core_line": source_document.core_line if source_document else None
            } if source_document else None,
            "color": get_scenario_color(scenario.scenario_type),
            "data": projections,
            "metadata": {
                "total_years": len(projections),
                "historical_years": len([p for p in projections if p['year'] <= pd.Timestamp.now().year]) if projections else 0,
                "future_years": len([p for p in projections if p['year'] > pd.Timestamp.now().year]) if projections else 0,
                "indicators": list(projections[0]['values'].keys()) if projections and len(projections) > 0 else []
            }
        }

        return scenario_details

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo detalles del escenario {scenario_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener detalles del escenario"
        )

def get_scenario_color(scenario_type: str) -> str:
    """Colores por tipo de escenario"""
    colors = {
        "tendencial": "#3B82F6",  # Azul
        "optimista": "#10B981",   # Verde
        "pesimista": "#EF4444"    # Rojo
    }
    return colors.get(scenario_type, "#6B7280")
