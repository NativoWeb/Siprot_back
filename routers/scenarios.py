from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from pydantic import BaseModel
from models import Document, User, Scenario, ScenarioProjection, ScenarioConfiguration
from routers.auth import get_db, require_role
from scenario_engine import ScenarioEngine, ScenarioType
from dependencies import get_current_user
from schemas import ScenarioConfigurationUpdate
import pandas as pd
import os
import logging
import chardet
import json

router = APIRouter(prefix="/scenarios", tags=["Escenarios"])
logger = logging.getLogger(__name__)


def sanitize_float(value):
    """Convierte valores no JSON-compliant a valores seguros"""
    import numpy as np
    import math
    
    if value is None:
        return 0.0
    
    try:
        float_val = float(value)
        if math.isinf(float_val) or math.isnan(float_val):
            return 0.0
        return float_val
    except (ValueError, TypeError, OverflowError):
        return 0.0


def sanitize_projection_data(projections: List[Dict]) -> List[Dict]:
    """Sanitiza los datos de proyecciones para asegurar compatibilidad JSON"""
    sanitized = []
    
    for proj in projections:
        sanitized_proj = {
            'year': int(proj.get('year', 0)),
            'sector': str(proj.get('sector', 'General')),
            'base_value': sanitize_float(proj.get('base_value', 0)),
            'multiplier': sanitize_float(proj.get('multiplier', 1.0)),
            'values': {}
        }
        
        values = proj.get('values', {})
        if isinstance(values, dict):
            for key, val in values.items():
                sanitized_proj['values'][str(key)] = sanitize_float(val)
        
        sanitized.append(sanitized_proj)
    
    return sanitized


def save_scenario_parameters_to_config(
    db: Session, 
    scenario_type: str, 
    parameters: Dict[str, float], 
    user_id: int
):
    """
    Guarda los parámetros personalizados en la tabla scenario_configurations
    """
    try:
        for param_name, param_value in parameters.items():
            config = db.query(ScenarioConfiguration).filter(
                ScenarioConfiguration.scenario_type == scenario_type,
                ScenarioConfiguration.parameter_name == param_name
            ).first()

            if config:
                config.parameter_value = float(param_value)
                config.updated_by = user_id
            else:
                config = ScenarioConfiguration(
                    scenario_type=scenario_type,
                    parameter_name=param_name,
                    parameter_value=float(param_value),
                    updated_by=user_id
                )
                db.add(config)
        
        db.flush()
        logger.info(f"Parámetros guardados en scenario_configurations para {scenario_type}")
        
    except Exception as e:
        logger.error(f"Error guardando configuración en BD: {e}")
        raise


def load_scenario_parameters_from_config(db: Session, scenario_type: str) -> Dict[str, float]:
    """
    Carga los parámetros desde la tabla scenario_configurations
    """
    try:
        configs = db.query(ScenarioConfiguration).filter(
            ScenarioConfiguration.scenario_type == scenario_type
        ).all()
        
        if configs:
            return {config.parameter_name: config.parameter_value for config in configs}
        return {}
        
    except Exception as e:
        logger.error(f"Error cargando configuración desde BD: {e}")
        return {}


class ScenarioGenerationRequest(BaseModel):
    """Modelo para la solicitud de generación de escenarios"""
    scenario_types: Optional[List[str]] = ["tendencial", "optimista", "pesimista"]
    years_ahead: int = 10
    parameters: Optional[Dict[str, float]] = None


def read_flexible_file(file_path: str, extension: str) -> pd.DataFrame:
    """
    Lee CSV o XLSX intentando detectar encoding y separador en CSV.
    """
    if extension.lower() == ".csv":
        with open(file_path, "rb") as f:
            sample = f.read(100000)
            result = chardet.detect(sample)
        detected_encoding = result.get("encoding") or "utf-8"

        separators = [";", ",", "\t", "|"]
        df = None

        for sep in separators:
            try:
                df_try = pd.read_csv(file_path, encoding=detected_encoding, sep=sep)
                if df_try.shape[1] > 1:
                    df = df_try
                    logger.debug(f"CSV leído con encoding={detected_encoding}, sep='{sep}'")
                    break
            except Exception:
                continue

        if df is None:
            try:
                df = pd.read_csv(file_path, encoding=detected_encoding)
            except Exception as e:
                raise ValueError(f"No se pudo leer CSV: {e}") from e
    else:
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            raise ValueError(f"No se pudo leer XLSX: {e}") from e

    if df is None or df.empty or df.shape[1] == 1:
        raise ValueError("Archivo inválido o vacío")

    df.columns = df.columns.astype(str).str.strip()

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.strip()
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
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
            }
            for doc in csv_documents
        ]
    except Exception as e:
        logger.exception("Error obteniendo archivos CSV")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener archivos CSV"
        )


@router.post("/generate/{document_id}")
def generate_scenarios_from_csv(
    document_id: int,
    request: ScenarioGenerationRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo"]))
):
    """
    Genera escenarios prospectivos basados en un archivo CSV/XLSX.
    Guarda las proyecciones Y los parámetros personalizados en BD.
    """
    scenario_types = request.scenario_types
    years_ahead = request.years_ahead
    custom_params = request.parameters or {}

    logger.info(f"Parámetros personalizados recibidos: {custom_params}")

    allowed_types = {"tendencial", "optimista", "pesimista"}
    bad_types = [t for t in scenario_types if t not in allowed_types]
    if bad_types:
        raise HTTPException(status_code=400, detail=f"Tipo(s) inválido(s): {bad_types}")

    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

        ext = (document.file_extension or "").lower()
        if ext not in ['.csv', '.xlsx']:
            raise HTTPException(status_code=400, detail="Debe ser CSV o XLSX")

        file_path = os.path.abspath(document.file_path)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Archivo no encontrado")

        try:
            df = read_flexible_file(file_path, ext)
        except Exception as e:
            logger.exception("Error leyendo archivo")
            raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {str(e)}")

        engine = ScenarioEngine(db)
        scenarios_data = {}

        for scenario_type in scenario_types:
            try:
                scenario_enum = ScenarioType(scenario_type)
                
                existing_scenario = db.query(Scenario).filter(
                    Scenario.scenario_type == scenario_type,
                    Scenario.name.like(f"%{document.title}%")
                ).first()

                scenario_config = engine.scenarios.get(scenario_enum)
                
                if not existing_scenario:
                    scenario_data = {
                        "name": f"{scenario_config.name} - {document.title}",
                        "scenario_type": scenario_type,
                        "description": f"{scenario_config.description} Basado en: {document.title}",
                        "parameters": {
                            "source_document_id": document_id,
                            "multipliers": scenario_config.multipliers,
                            "growth_rates": scenario_config.growth_rates,
                            "custom_parameters": custom_params
                        }
                    }
                    scenario = engine.create_scenario(scenario_data, current_user.id)
                else:
                    scenario = existing_scenario
                    if scenario.parameters:
                        scenario.parameters["custom_parameters"] = custom_params
                        db.commit()

                # NUEVO: Guardar parámetros en scenario_configurations
                if custom_params:
                    save_scenario_parameters_to_config(
                        db, 
                        scenario_type, 
                        custom_params, 
                        current_user.id
                    )
                    db.commit()

                projections = engine.generate_scenario_projections(
                    scenario.id, 
                    df, 
                    years_ahead,
                    custom_params=custom_params
                )

                if not isinstance(projections, list):
                    logger.warning(f"Projections for {scenario.id} is not a list")
                    projections = []
                
                projections = sanitize_projection_data(projections)

                try:
                    deleted = db.query(ScenarioProjection).filter(
                        ScenarioProjection.scenario_id == scenario.id
                    ).delete(synchronize_session=False)
                    
                    if deleted:
                        logger.debug(f"Eliminadas {deleted} proyecciones antiguas")
                    db.flush()

                    projection_objs = []
                    for p in projections:
                        year = p.get("year")
                        sector = p.get("sector", "General")
                        base_value_common = p.get("base_value", 0)
                        multiplier_common = p.get("multiplier", 1.0)
                        values = p.get("values", {})

                        if isinstance(values, (int, float)):
                            projection_objs.append(ScenarioProjection(
                                scenario_id=scenario.id,
                                sector=sector,
                                year=int(year),
                                projected_value=float(values),
                                base_value=float(base_value_common),
                                multiplier_applied=float(multiplier_common),
                                indicator_type="value"
                            ))
                        elif isinstance(values, dict):
                            for indicator, val in values.items():
                                try:
                                    projected_value = float(val) if val is not None else 0.0
                                except Exception:
                                    continue

                                projection_objs.append(ScenarioProjection(
                                    scenario_id=scenario.id,
                                    sector=sector,
                                    year=int(year),
                                    projected_value=projected_value,
                                    base_value=float(base_value_common),
                                    multiplier_applied=float(multiplier_common),
                                    indicator_type=str(indicator)
                                ))

                    if projection_objs:
                        db.add_all(projection_objs)
                        db.commit()
                        logger.info(f"Guardadas {len(projection_objs)} proyecciones")

                except Exception as persist_exc:
                    db.rollback()
                    logger.exception(f"Error guardando proyecciones: {persist_exc}")

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
                        "historical_years": len([p for p in projections if p.get('year', 0) <= pd.Timestamp.now().year]),
                        "future_years": len([p for p in projections if p.get('year', 0) > pd.Timestamp.now().year]),
                        "indicators": list(projections[0].get('values', {}).keys()) if projections else []
                    }
                }

                logger.info(f"Escenario {scenario_type} generado con {len(projections)} puntos")
                
            except Exception as e:
                logger.exception(f"Error generando {scenario_type}: {e}")
                continue

        if not scenarios_data:
            raise HTTPException(status_code=500, detail="No se pudieron generar escenarios")

        try:
            json.dumps(scenarios_data)
        except (ValueError, TypeError) as e:
            logger.error(f"Error serializando JSON: {e}")
            raise HTTPException(status_code=500, detail="Error en formato de datos")

        return scenarios_data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error inesperado")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.get("/configurations/{scenario_type}")
def get_scenario_configuration(
    scenario_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo", "instructor"]))
):
    """
    Obtiene los parámetros guardados para un tipo de escenario
    """
    try:
        parameters = load_scenario_parameters_from_config(db, scenario_type)
        
        return {
            "scenario_type": scenario_type,
            "parameters": parameters
        }
    except Exception as e:
        logger.exception(f"Error obteniendo configuración: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo configuración")


@router.post("/configurations/set")
def set_scenario_configuration(
    request: ScenarioConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin", "planeacion"]))
):
    """
    Crea o actualiza los parámetros de un tipo de escenario
    """
    try:
        save_scenario_parameters_to_config(
            db, 
            request.scenario_type.value, 
            request.parameters, 
            current_user.id
        )
        db.commit()
        
        return {
            "message": "Configuración guardada correctamente",
            "scenario_type": request.scenario_type.value,
            "parameters": request.parameters
        }

    except Exception as e:
        db.rollback()
        logger.exception(f"Error guardando configuración: {e}")
        raise HTTPException(status_code=500, detail="Error guardando configuración")


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
            raise HTTPException(status_code=404, detail="Algunos escenarios no encontrados")

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
        logger.exception("Error comparando escenarios")
        raise HTTPException(status_code=500, detail="Error comparando escenarios")


@router.get("/list", response_model=List[Dict])
def list_existing_scenarios(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo", "instructor"]))
):
    """Lista todos los escenarios existentes"""
    try:
        scenarios = db.query(Scenario).filter(
            Scenario.is_active == True
        ).order_by(Scenario.created_at.desc()).all()

        scenarios_list = []
        for scenario in scenarios:
            creator = db.query(User).filter(User.id == scenario.created_by).first()

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
                "created_at": scenario.created_at.isoformat() if scenario.created_at else None,
                "created_by": {
                    "id": creator.id if creator else None,
                    "email": creator.email if creator else "Usuario eliminado",
                    "role": creator.role if creator else None,
                    "full_name": f"{creator.first_name} {creator.last_name}".strip() if creator and creator.first_name else (creator.email if creator else "Usuario eliminado")
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
        logger.exception("Error listando escenarios")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo lista de escenarios"
        )


@router.get("/details/{scenario_id}")
def get_scenario_details(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo", "instructor"]))
):
    """Obtiene los detalles completos de un escenario específico"""
    try:
        scenario = db.query(Scenario).filter(
            Scenario.id == scenario_id,
            Scenario.is_active == True
        ).first()

        if not scenario:
            raise HTTPException(status_code=404, detail="Escenario no encontrado")

        creator = db.query(User).filter(User.id == scenario.created_by).first()

        projections_q = db.query(ScenarioProjection).filter(
            ScenarioProjection.scenario_id == scenario_id
        ).order_by(ScenarioProjection.year.asc()).all()
        
        projections = []
        if projections_q:
            by_year = {}
            for p in projections_q:
                y = p.year
                if y not in by_year:
                    by_year[y] = {"year": y, "sector": p.sector, "values": {}}
                by_year[y]["values"][p.indicator_type] = sanitize_float(p.projected_value)
            projections = [by_year[y] for y in sorted(by_year.keys())]
            projections = sanitize_projection_data(projections)
        else:
            source_document = None
            if scenario.parameters and 'source_document_id' in scenario.parameters:
                doc_id = scenario.parameters['source_document_id']
                source_document = db.query(Document).filter(Document.id == doc_id).first()

            if source_document:
                try:
                    file_path = os.path.abspath(source_document.file_path)
                    if os.path.exists(file_path):
                        df = read_flexible_file(file_path, source_document.file_extension)
                        engine = ScenarioEngine(db)
                        custom_params = scenario.parameters.get('custom_parameters', {})
                        projections = engine.generate_scenario_projections(
                            scenario.id, df, 10, custom_params=custom_params
                        )
                        projections = sanitize_projection_data(projections)
                except Exception as e:
                    logger.warning(f"No se pudieron regenerar proyecciones: {e}")

        scenario_details = {
            "id": scenario.id,
            "name": scenario.name,
            "scenario_type": scenario.scenario_type,
            "description": scenario.description,
            "parameters": scenario.parameters,
            "created_at": scenario.created_at.isoformat() if scenario.created_at else None,
            "updated_at": scenario.updated_at.isoformat() if scenario.updated_at else None,
            "created_by": {
                "id": creator.id if creator else None,
                "email": creator.email if creator else "Usuario eliminado",
                "role": creator.role if creator else None,
                "full_name": f"{creator.first_name} {creator.last_name}".strip() if creator and creator.first_name else (creator.email if creator else "Usuario eliminado")
            },
            "source_document": None,
            "color": get_scenario_color(scenario.scenario_type),
            "data": projections,
            "metadata": {
                "total_years": len(projections),
                "historical_years": len([p for p in projections if p.get('year', 0) <= pd.Timestamp.now().year]),
                "future_years": len([p for p in projections if p.get('year', 0) > pd.Timestamp.now().year]),
                "indicators": list(projections[0].get('values', {}).keys()) if projections else []
            }
        }

        if scenario.parameters and 'source_document_id' in scenario.parameters:
            doc_id = scenario.parameters['source_document_id']
            src_doc = db.query(Document).filter(Document.id == doc_id).first()
            if src_doc:
                scenario_details["source_document"] = {
                    "id": src_doc.id,
                    "title": src_doc.title,
                    "filename": src_doc.original_filename,
                    "year": src_doc.year,
                    "sector": src_doc.sector,
                    "core_line": src_doc.core_line
                }

        return scenario_details

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error obteniendo detalles del escenario {scenario_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo detalles del escenario"
        )


def get_scenario_color(scenario_type: str) -> str:
    """Colores por tipo de escenario"""
    colors = {
        "tendencial": "#3B82F6",
        "optimista": "#10B981",
        "pesimista": "#EF4444"
    }
    return colors.get(scenario_type, "#6B7280")