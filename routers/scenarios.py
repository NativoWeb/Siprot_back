from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import json
import io
from datetime import datetime

from database import get_db
from dependencies import get_current_user
from routers.auth import require_role
from models import User, Scenario, ScenarioProjection
from schemas import (
    ScenarioCreate, ScenarioUpdate, ScenarioResponse,
    ProjectionRequest, ScenarioProjectionResponse, ScenarioComparisonResponse,
    ScenarioConfigurationUpdate, ScenarioExportRequest
)
from scenario_engine import ScenarioEngine
from routers.audit import AuditLogger, AuditAction

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

@router.get("/", response_model=List[ScenarioResponse])
def get_scenarios(
    skip: int = 0,
    limit: int = 100,
    scenario_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener lista de escenarios (R4.1)
    Todos los usuarios autenticados pueden ver escenarios
    """
    query = db.query(Scenario).filter(Scenario.is_active == True)
    
    if scenario_type:
        query = query.filter(Scenario.scenario_type == scenario_type)
    
    scenarios = query.offset(skip).limit(limit).all()
    
    # Log de consulta
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.RESOURCE_READ,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="SCENARIO",
        details={"count": len(scenarios), "filters": {"scenario_type": scenario_type}}
    )
    
    return scenarios

@router.post("/", response_model=ScenarioResponse)
def create_scenario(
    scenario: ScenarioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    """
    Crear nuevo escenario (R4.3)
    Solo usuarios de Planeación y Superadmin pueden crear escenarios
    """
    engine = ScenarioEngine(db)
    
    scenario_data = {
        "name": scenario.name,
        "scenario_type": scenario.scenario_type.value,
        "description": scenario.description,
        "parameters": scenario.parameters.dict()
    }
    
    new_scenario = engine.create_scenario(scenario_data, current_user.id)
    
    # Log de creación
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.RESOURCE_CREATE,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="SCENARIO",
        resource_id=str(new_scenario.id),
        new_values=scenario_data
    )
    
    return new_scenario

@router.put("/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario_id: int,
    scenario_update: ScenarioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["planeacion", "superadmin"]))
):
    """
    Actualizar escenario existente (R4.3)
    Solo usuarios de Planeación y Superadmin pueden modificar escenarios
    """
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Escenario no encontrado")
    
    # Guardar valores anteriores para auditoría
    old_values = {
        "name": scenario.name,
        "description": scenario.description,
        "parameters": scenario.parameters,
        "is_active": scenario.is_active
    }
    
    # Actualizar campos
    update_data = scenario_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "parameters" and value:
            setattr(scenario, field, value.dict())
        else:
            setattr(scenario, field, value)
    
    scenario.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(scenario)
    
    # Log de actualización
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.RESOURCE_UPDATE,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="SCENARIO",
        resource_id=str(scenario_id),
        old_values=old_values,
        new_values=update_data
    )
    
    return scenario

@router.post("/projections", response_model=List[ScenarioProjectionResponse])
def generate_projections(
    request: ProjectionRequest,
    historical_data: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generar proyecciones para escenarios (R4.2)
    Todos los usuarios autenticados pueden generar proyecciones
    """
    try:
        # Leer datos históricos del archivo
        content = historical_data.file.read()
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        
        engine = ScenarioEngine(db)
        engine.initialize_model()
        
        results = []
        for scenario_id in request.scenario_ids:
            scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
            if not scenario:
                continue
            
            projections = engine.generate_scenario_projections(
                scenario_id, df, request.years_ahead
            )
            
            # Calcular resumen
            summary = {
                "total_projections": len(projections),
                "sectors_analyzed": len(set(p['sector'] for p in projections)),
                "years_projected": request.years_ahead
            }
            
            results.append(ScenarioProjectionResponse(
                scenario_id=scenario_id,
                scenario_name=scenario.name,
                scenario_type=scenario.scenario_type,
                projections=projections,
                summary=summary
            ))
        
        # Log de generación de proyecciones
        AuditLogger.log_user_action(
            db=db,
            action=AuditAction.RESOURCE_CREATE,
            user_id=current_user.id,
            user_email=current_user.email,
            resource_type="PROJECTION",
            details={
                "scenario_ids": request.scenario_ids,
                "years_ahead": request.years_ahead,
                "total_projections": sum(len(r.projections) for r in results)
            }
        )
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando proyecciones: {str(e)}"
        )

@router.post("/compare", response_model=ScenarioComparisonResponse)
def compare_scenarios(
    scenario_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Comparar múltiples escenarios (R4.2)
    Todos los usuarios autenticados pueden comparar escenarios
    """
    engine = ScenarioEngine(db)
    comparison_result = engine.compare_scenarios(scenario_ids)
    
    # Log de comparación
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.RESOURCE_READ,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="SCENARIO_COMPARISON",
        details={"scenario_ids": scenario_ids}
    )
    
    return comparison_result

@router.post("/export")
def export_scenarios(
    request: ScenarioExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exportar datos de escenarios (R4.6)
    Todos los usuarios autenticados pueden exportar datos
    """
    try:
        scenarios_data = []
        
        for scenario_id in request.scenario_ids:
            scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
            if scenario:
                projections = db.query(ScenarioProjection).filter(
                    ScenarioProjection.scenario_id == scenario_id
                ).all()
                
                scenarios_data.append({
                    "scenario": {
                        "id": scenario.id,
                        "name": scenario.name,
                        "type": scenario.scenario_type,
                        "description": scenario.description,
                        "parameters": scenario.parameters
                    },
                    "projections": [
                        {
                            "sector": p.sector,
                            "year": p.year,
                            "indicator_type": p.indicator_type,
                            "base_value": p.base_value,
                            "projected_value": p.projected_value,
                            "multiplier_applied": p.multiplier_applied
                        } for p in projections
                    ]
                })
        
        # Log de exportación
        AuditLogger.log_user_action(
            db=db,
            action=AuditAction.RESOURCE_EXPORT,
            user_id=current_user.id,
            user_email=current_user.email,
            resource_type="SCENARIO",
            details={
                "scenario_ids": request.scenario_ids,
                "format": request.format,
                "include_charts": request.include_charts
            }
        )
        
        if request.format == "json":
            return {"data": scenarios_data, "format": "json"}
        elif request.format == "csv":
            # Convertir a CSV
            csv_data = []
            for scenario_data in scenarios_data:
                for projection in scenario_data["projections"]:
                    csv_data.append({
                        "scenario_name": scenario_data["scenario"]["name"],
                        "scenario_type": scenario_data["scenario"]["type"],
                        **projection
                    })
            
            df = pd.DataFrame(csv_data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            
            return {"data": csv_buffer.getvalue(), "format": "csv"}
        
        return {"data": scenarios_data, "format": request.format}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error exportando escenarios: {str(e)}"
        )

@router.post("/initialize-defaults")
def initialize_default_scenarios(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["superadmin"]))
):
    """
    Inicializar escenarios predefinidos (R4.1)
    Solo Superadmin puede inicializar escenarios predefinidos
    """
    engine = ScenarioEngine(db)
    engine.initialize_default_scenarios(current_user.id)
    
    # Log de inicialización
    AuditLogger.log_user_action(
        db=db,
        action=AuditAction.SYSTEM_CONFIGURATION,
        user_id=current_user.id,
        user_email=current_user.email,
        resource_type="SCENARIO",
        details={"action": "initialize_defaults"}
    )
    
    return {"message": "Escenarios predefinidos inicializados correctamente"}
