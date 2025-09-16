from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict
from models import Document, User, Scenario
from routers.auth import get_db, require_role
from scenario_engine import ScenarioEngine, ScenarioType
import pandas as pd
import os
import logging

router = APIRouter(prefix="/scenarios", tags=["Escenarios"])
logger = logging.getLogger(__name__)

# 🔹 Nueva función para leer archivos flexibles
def read_flexible_file(file_path: str, extension: str) -> pd.DataFrame:
    if extension == ".csv":
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
        separators = [";", ",", "\t", "|"]
        df = None

        for encoding in encodings:
            for sep in separators:
                try:
                    df = pd.read_csv(file_path, encoding=encoding, sep=sep)
                    if not df.empty and len(df.columns) > 1:
                        logger.info(f"CSV leído con encoding={encoding}, sep='{sep}'")
                        break
                except Exception:
                    continue
            if df is not None and not df.empty:
                break
    else:  # XLSX
        df = pd.read_excel(file_path)

    if df is None or df.empty:
        raise ValueError("No se pudo leer el archivo con ninguna configuración")

    # 🔹 Limpieza de columnas numéricas con coma y %
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


def get_scenario_color(scenario_type: str) -> str:
    """Colores por tipo de escenario"""
    colors = {
        "tendencial": "#3B82F6",  # Azul
        "optimista": "#10B981",   # Verde
        "pesimista": "#EF4444"    # Rojo
    }
    return colors.get(scenario_type, "#6B7280")
