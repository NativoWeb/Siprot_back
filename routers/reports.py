from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import os

from database import get_db
from schemas import (
    SolicitudReporte, ReporteResponse, TipoReporteInfo,
    IndicadorResponse, TipoReporte
)
from models import Reporte, Indicador
from services.report_service import ReportService
from services.data_service import DataService

# ¡IMPORTANTE! Asume que tienes una función para obtener el usuario actual
# Ajusta la importación según tu sistema de auth existente
from routers.auth import get_current_user  # ← Ajusta según tu implementación

router = APIRouter(prefix="/reportes", tags=["reportes"])

@router.get("/tipos", response_model=List[TipoReporteInfo])
async def obtener_tipos_reportes():
    """Obtiene los tipos de reportes disponibles"""
    return [
        TipoReporteInfo(
            tipo=TipoReporte.INDICADORES,
            nombre="Reporte de Indicadores",
            descripcion="Análisis del estado actual de indicadores estratégicos",
            tiempo_estimado="2-3 minutos",
            opciones_disponibles=["Filtro por indicadores", "Gráficos históricos", "Recomendaciones"]
        ),
        TipoReporteInfo(
            tipo=TipoReporte.PROSPECTIVA,
            nombre="Reporte de Prospectiva",
            descripcion="Análisis prospectivo territorial y sectorial",
            tiempo_estimado="5-7 minutos",
            opciones_disponibles=["Escenarios futuros", "Análisis DOFA", "Proyecciones"]
        ),
        TipoReporteInfo(
            tipo=TipoReporte.OFERTA_EDUCATIVA,
            nombre="Análisis de Oferta Educativa",
            descripcion="Estado actual y proyecciones de la oferta formativa",
            tiempo_estimado="3-4 minutos",
            opciones_disponibles=["Por sectores", "Análisis de brechas", "Recomendaciones"]
        ),
        TipoReporteInfo(
            tipo=TipoReporte.CONSOLIDADO,
            nombre="Reporte Consolidado",
            descripcion="Reporte integral con todos los componentes",
            tiempo_estimado="8-10 minutos",
            opciones_disponibles=["Resumen ejecutivo", "Todos los análisis", "Anexos"]
        )
    ]

@router.post("/generar", response_model=ReporteResponse)
async def generar_reporte(
    solicitud: SolicitudReporte,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        usuario_id = current_user.id
        
        nuevo_reporte = Reporte(
            tipo=solicitud.tipo.value,
            usuario_id=usuario_id,
            parametros=solicitud.parametros.dict(),
            estado="generando"
        )
        db.add(nuevo_reporte)
        db.commit()
        db.refresh(nuevo_reporte)

        report_service = ReportService(db)
        background_tasks.add_task(
            report_service.generar_reporte_background,
            nuevo_reporte.id,
            solicitud.tipo,
            solicitud.parametros
        )
        return ReporteResponse.from_orm(nuevo_reporte)
    except Exception as e:
        print("Error al generar reporte:", e)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/", response_model=List[ReporteResponse])
async def listar_reportes(
    skip: int = 0,
    limit: int = 100,
    admin_view: bool = False,  # ← Para admin: ver todos los reportes
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # ← Usuario autenticado
):
    """Lista los reportes generados por el usuario actual"""
    
    query = db.query(Reporte)
    
    # Si no es admin, solo mostrar sus propios reportes
    if not admin_view or not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        query = query.filter(Reporte.usuario_id == current_user.id)
    
    reportes = query.order_by(Reporte.fecha_generacion.desc()).offset(skip).limit(limit).all()
    return [ReporteResponse.from_orm(reporte) for reporte in reportes]

@router.get("/mis-reportes", response_model=List[ReporteResponse])
async def mis_reportes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Lista SOLO los reportes del usuario actual"""
    
    reportes = db.query(Reporte)\
                .filter(Reporte.usuario_id == current_user.id)\
                .order_by(Reporte.fecha_generacion.desc())\
                .offset(skip)\
                .limit(limit)\
                .all()
    
    return [ReporteResponse.from_orm(reporte) for reporte in reportes]

@router.get("/{reporte_id}", response_model=ReporteResponse)
async def obtener_reporte(
    reporte_id: int, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Obtiene un reporte específico (solo si es del usuario)"""
    
    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    
    # Verificar que el reporte pertenece al usuario (seguridad)
    if reporte.usuario_id != current_user.id:
        # Opción 1: Error de permisos
        raise HTTPException(status_code=403, detail="No tienes permisos para ver este reporte")
        
        # Opción 2: Solo admins pueden ver reportes de otros
        # if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        #     raise HTTPException(status_code=403, detail="No tienes permisos para ver este reporte")
    
    return ReporteResponse.from_orm(reporte)

@router.get("/indicadores/", response_model=List[IndicadorResponse])
async def obtener_indicadores(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # ← Verificar autenticación
):
    """Obtiene la lista de indicadores disponibles"""
    data_service = DataService(db)
    return data_service.obtener_indicadores()

@router.get("/{reporte_id}/descargar")
async def descargar_reporte(
    reporte_id: int, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Descarga el archivo PDF del reporte (solo si es del usuario)"""
    
    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    
    # Verificar permisos
    if reporte.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permisos para descargar este reporte")
    
    if not reporte.archivo_path or not os.path.exists(reporte.archivo_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return FileResponse(
        path=reporte.archivo_path,
        filename=f"reporte_{reporte.id}_{reporte.tipo}.pdf",
        media_type="application/pdf"
    )

@router.delete("/{reporte_id}")
async def eliminar_reporte(
    reporte_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Elimina un reporte (solo el propietario)"""
    
    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    
    if reporte.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permisos para eliminar este reporte")
    
    # Eliminar archivo físico
    if reporte.archivo_path and os.path.exists(reporte.archivo_path):
        os.remove(reporte.archivo_path)
    
    # Eliminar registro de BD
    db.delete(reporte)
    db.commit()
    
    return {"message": "Reporte eliminado exitosamente"}

# Endpoint solo para administradores
@router.get("/admin/todos", response_model=List[ReporteResponse])
async def listar_todos_reportes_admin(
    skip: int = 0,
    limit: int = 100,
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Lista TODOS los reportes (solo admin)"""
    
    # Verificar que es admin
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Solo administradores pueden acceder")
    
    query = db.query(Reporte)
    
    if usuario_id:
        query = query.filter(Reporte.usuario_id == usuario_id)
    
    reportes = query.order_by(Reporte.fecha_generacion.desc()).offset(skip).limit(limit).all()
    return [ReporteResponse.from_orm(reporte) for reporte in reportes]