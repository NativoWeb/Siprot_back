from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from models import Document, User, Scenario, ScenarioProjection
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
    """
    Lee CSV o XLSX intentando detectar encoding y separador en CSV.
    Lanza ValueError si no puede leer o si el DataFrame es inválido.
    """
    if extension.lower() == ".csv":
        # Detect encoding (leer una porción para no cargar todo en memoria)
        with open(file_path, "rb") as f:
            sample = f.read(100000)
            result = chardet.detect(sample)
        detected_encoding = result.get("encoding") or "utf-8"

        separators = [";", ",", "\t", "|"]
        df = None
        last_exception = None

        for sep in separators:
            try:
                df_try = pd.read_csv(file_path, encoding=detected_encoding, sep=sep)
                if df_try.shape[1] > 1:
                    df = df_try
                    logger.debug(f"CSV leído con encoding={detected_encoding}, sep='{sep}'")
                    break
            except Exception as e:
                last_exception = e
                continue

        if df is None:
            # intentar sin especificar separador (lectura por defecto)
            try:
                df = pd.read_csv(file_path, encoding=detected_encoding)
            except Exception as e:
                raise ValueError(f"No se pudo leer CSV - probar separador/encoding. Error: {e}") from e

    else:
        # Excel
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            raise ValueError(f"No se pudo leer XLSX: {e}") from e

    if df is None or df.empty or df.shape[1] == 1:
        raise ValueError("No se pudo leer el archivo correctamente (verifique el separador y formato)")

    # Limpieza y normalización de columnas
    df.columns = df.columns.astype(str).str.strip()

    # Normalizar texto y convertir números donde sea posible
    for col in df.columns:
        if df[col].dtype == object:
            # quitar % y normalizar separadores decimales
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("%", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.strip()
            )
            # intentar convertir a numérico, si falla se queda como object
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
    scenario_types: Optional[List[str]] = None,
    years_ahead: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "administrativo"]))
):
    """
    Genera escenarios prospectivos basados en un archivo CSV/XLSX.
    Guarda las proyecciones en la tabla `scenario_projections`.
    """
    if scenario_types is None:
        scenario_types = ["tendencial", "optimista", "pesimista"]

    # Validar tipos
    allowed_types = {t.value if isinstance(t, ScenarioType) else t for t in [ScenarioType.TENDENCIAL, ScenarioType.OPTIMISTA, ScenarioType.PESIMISTA]}
    # Adjusting allowed_types above depends on your enum implementation; if ScenarioType uses strings, you can set: allowed_types = {"tendencial","optimista","pesimista"}
    # Fallback safe set:
    allowed_types = {"tendencial", "optimista", "pesimista"}

    bad_types = [t for t in scenario_types if t not in allowed_types]
    if bad_types:
        raise HTTPException(status_code=400, detail=f"Tipo(s) de escenario inválido(s): {bad_types}")

    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

        ext = (document.file_extension or "").lower()
        if ext not in ['.csv', '.xlsx']:
            raise HTTPException(status_code=400, detail="El archivo debe ser CSV o XLSX")

        file_path = os.path.abspath(document.file_path)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Archivo no encontrado en el servidor")

        try:
            df = read_flexible_file(file_path, ext)
        except Exception as e:
            logger.exception("Error leyendo archivo")
            raise HTTPException(
                status_code=400,
                detail=f"Error al leer el archivo: {str(e)}. Verifique que el archivo tenga el formato correcto."
            )

        engine = ScenarioEngine(db)
        scenarios_data = {}

        for scenario_type in scenario_types:
            try:
                # Convertir a Enum si hace falta; si ScenarioType espera string, ajusta
                try:
                    scenario_enum = ScenarioType(scenario_type)
                except Exception:
                    # Si ScenarioType no recibe la cadena, intentar por nombre
                    # Ajusta según la implementación de tu ScenarioType
                    scenario_enum = None

                # Buscar escenario existente (evita duplicados por documento)
                existing_scenario = db.query(Scenario).filter(
                    Scenario.scenario_type == scenario_type,
                    Scenario.name.like(f"%{document.title}%")
                ).first()

                if not existing_scenario:
                    scenario_data = {
                        "name": f"{engine.scenarios.get(scenario_enum).name if scenario_enum else scenario_type} - {document.title}",
                        "scenario_type": scenario_type,
                        "description": (engine.scenarios.get(scenario_enum).description if scenario_enum else scenario_type) + f" Basado en: {document.title}",
                        "parameters": {
                            "source_document_id": document_id,
                            "multipliers": (engine.scenarios.get(scenario_enum).multipliers if scenario_enum else {}),
                            "growth_rates": (engine.scenarios.get(scenario_enum).growth_rates if scenario_enum else {})
                        }
                    }
                    scenario = engine.create_scenario(scenario_data, current_user.id)
                else:
                    scenario = existing_scenario

                # Generar proyecciones con el motor
                projections = engine.generate_scenario_projections(scenario.id, df, years_ahead)
                if not isinstance(projections, list):
                    logger.warning(f"Projections for scenario {scenario.id} is not a list; skipping")
                    projections = []

                # Guardar proyecciones en BD (borrar anteriores para este scenario_id)
                try:
                    # borrar proyecciones antiguas
                    deleted = db.query(ScenarioProjection).filter(ScenarioProjection.scenario_id == scenario.id).delete(synchronize_session=False)
                    if deleted:
                        logger.debug(f"Se eliminaron {deleted} proyecciones antiguas para el escenario {scenario.id}")
                    db.flush()

                    projection_objs = []
                    for p in projections:
                        # cada 'p' debe tener al menos: year, values (dict por indicador), opcional sector, base_value, multiplier
                        year = p.get("year")
                        sector = p.get("sector", p.get("sector_name", "General"))
                        base_value_common = p.get("base_value", 0)
                        multiplier_common = p.get("multiplier", p.get("multiplier_applied", 1.0))
                        values = p.get("values", {})

                        # Si 'values' es un number único (no dict), intentar mapear a un indicador por defecto
                        if isinstance(values, (int, float)):
                            # crear un projection por defecto con indicador "value"
                            projection_objs.append(ScenarioProjection(
                                scenario_id=scenario.id,
                                sector=sector,
                                year=int(year),
                                projected_value=float(values),
                                base_value=float(base_value_common or 0),
                                multiplier_applied=float(multiplier_common or 1.0),
                                indicator_type=p.get("indicator", "value")
                            ))
                        elif isinstance(values, dict):
                            for indicator, val in values.items():
                                try:
                                    projected_value = float(val) if val is not None else 0.0
                                except Exception:
                                    # si no se puede convertir, saltar
                                    logger.debug(f"Valor no numérico para indicador {indicator} año {year}: {val}")
                                    continue

                                projection_objs.append(ScenarioProjection(
                                    scenario_id=scenario.id,
                                    sector=sector,
                                    year=int(year),
                                    projected_value=projected_value,
                                    base_value=float(base_value_common or 0),
                                    multiplier_applied=float(multiplier_common or 1.0),
                                    indicator_type=str(indicator)
                                ))
                        else:
                            logger.debug(f"Estructura de 'values' inesperada en proyección: {type(values)}")

                    if projection_objs:
                        db.add_all(projection_objs)
                        db.commit()
                        logger.info(f"Guardadas {len(projection_objs)} proyecciones para escenario {scenario.id}")
                    else:
                        # Si no hay proyecciones, hacemos rollback de la eliminación para no dejar estado inconsistente
                        db.rollback()
                        logger.warning(f"No se generaron proyecciones válidas para escenario {scenario.id}")
                except Exception as persist_exc:
                    db.rollback()
                    logger.exception(f"Error guardando proyecciones para scenario {scenario.id}: {persist_exc}")
                    # continuar con el siguiente escenario sin fallar todo el proceso

                # Preparar respuesta
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
                        "indicators": list(projections[0].get('values', {}).keys()) if projections and projections[0].get('values') else []
                    }
                }

                logger.info(f"Escenario {scenario_type} (id={scenario.id}) generado con {len(projections)} puntos")
            except Exception as e:
                logger.exception(f"Error generando escenario {scenario_type} para documento {document_id}: {e}")
                # No abortamos todo el loop, pasamos al siguiente tipo
                continue

        if not scenarios_data:
            raise HTTPException(status_code=500, detail="No se pudieron generar escenarios")

        logger.info(f"Escenarios generados exitosamente para documento {document_id}")
        return scenarios_data

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error inesperado en generación de escenarios")
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

        # Obtener proyecciones desde BD
        projections_q = db.query(ScenarioProjection).filter(ScenarioProjection.scenario_id == scenario_id).order_by(ScenarioProjection.year.asc()).all()
        projections = []
        if projections_q:
            # convertir a la estructura que usan tus endpoints (year + values dict)
            # agrupamos por year
            by_year = {}
            for p in projections_q:
                y = p.year
                if y not in by_year:
                    by_year[y] = {"year": y, "sector": p.sector, "values": {}}
                by_year[y]["values"][p.indicator_type] = p.projected_value
            projections = [by_year[y] for y in sorted(by_year.keys())]
        else:
            # Si no hay proyecciones guardadas, intentar regenerar si hay documento fuente
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
                        projections = engine.generate_scenario_projections(scenario.id, df, 10)
                    else:
                        projections = []
                except Exception as e:
                    logger.warning(f"No se pudieron regenerar proyecciones para escenario {scenario_id}: {e}")
                    projections = []
            else:
                projections = []

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
                "historical_years": len([p for p in projections if p.get('year', 0) <= pd.Timestamp.now().year]) if projections else 0,
                "future_years": len([p for p in projections if p.get('year', 0) > pd.Timestamp.now().year]) if projections else 0,
                "indicators": list(projections[0].get('values', {}).keys()) if projections and len(projections) > 0 else []
            }
        }

        # Adjuntar source_document si existe
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
