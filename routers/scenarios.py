from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from models import Document, User, Scenario
from routers.auth import get_db, require_role
from scenario_engine import ScenarioEngine, ScenarioType
import pandas as pd
import os
import logging

router = APIRouter(prefix="/scenarios", tags=["Escenarios"])
logger = logging.getLogger(__name__)

@router.get("/csv-files", response_model=List[Dict])
def get_csv_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo", "instructor"]))
):
    """Obtiene la lista de archivos CSV disponibles para análisis de escenarios"""
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
    """Genera escenarios prospectivos basados en un archivo CSV específico"""
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Documento no encontrado"
            )
        
        if document.file_extension not in ['.csv', '.xlsx']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo debe ser CSV o XLSX"
            )
        
        # Convertir siempre a ruta absoluta
        file_path = os.path.abspath(document.file_path)

        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Archivo no encontrado en el servidor"
            )
        
        try:
            if document.file_extension == '.csv':
                df = pd.read_csv(file_path)
            else:  # .xlsx
                df = pd.read_excel(file_path)
        except Exception as e:
            logger.error(f"Error leyendo archivo {file_path}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error al leer el archivo. Verifique el formato."
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
                    # Crear nuevo escenario
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
                
                # Generar proyecciones específicas para este escenario
                projections = engine.generate_scenario_projections(
                    scenario.id, df, years_ahead
                )
                
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
                
                logger.info(f"Escenario {scenario_type} generado exitosamente con {len(projections)} puntos de datos")
                
            except ValueError as ve:
                logger.error(f"Tipo de escenario inválido: {scenario_type} - {str(ve)}")
                continue
            except Exception as e:
                logger.error(f"Error generando escenario {scenario_type}: {str(e)}")
                import traceback
                logger.error(f"Traceback completo: {traceback.format_exc()}")
                continue
        
        if not scenarios_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudieron generar escenarios"
            )
        
        logger.info(f"Escenarios generados exitosamente para documento {document_id} por usuario {current_user.email}")
        return scenarios_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado generando escenarios: {str(e)}")
        import traceback
        logger.error(f"Traceback completo: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Algunos escenarios no fueron encontrados"
            )
        
        engine = ScenarioEngine(db)
        comparison_data = []
        
        for scenario in scenarios:
            # Aquí podrías regenerar las proyecciones o usar datos almacenados
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al comparar escenarios"
        )

def get_scenario_color(scenario_type: str) -> str:
    """Obtiene el color asociado a cada tipo de escenario"""
    colors = {
        "tendencial": "#3B82F6",  # Azul
        "optimista": "#10B981",   # Verde
        "pesimista": "#EF4444"    # Rojo
    }
    return colors.get(scenario_type, "#6B7280")  # Gris por defecto