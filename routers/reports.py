from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query
from fastapi.responses import Response, FileResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta
import os
import logging
import mimetypes
import pathlib

from database import get_db
from schemas import (
    SolicitudReporte, ReporteResponse, TipoReporteInfo,
    IndicadorResponse, TipoReporte
)
from models import Reporte, Indicador
from services.improved_report_service import ImprovedReportService
from services.data_collector_service import IntegratedDataCollectorService

# Auth / permisos
from routers.auth import get_current_user, require_role
from routers.audit import AuditLogger, AuditAction

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reportes", tags=["reportes"])

def serialize_any(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: serialize_any(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_any(v) for v in obj]
    return obj

def _sanitize_filename(name: str) -> str:
    """Sanitiza un nombre de archivo básico (quita rutas, caracteres raros)."""
    base = os.path.basename(name or "")
    safe = "".join(c if c.isalnum() or c in (" ", ".", "_", "-") else "_" for c in base)
    return safe.replace(" ", "_") or "reporte.pdf"

def _serve_binary_pdf(content: bytes, filename: str, inline: bool = False):
    disposition = "inline" if inline else "attachment"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{_sanitize_filename(filename)}"'
        }
    )

# -----------------------
# Tipos de reportes
# -----------------------
@router.get("/tipos", response_model=List[TipoReporteInfo])
async def obtener_tipos_reportes():
    return [
        TipoReporteInfo(
            tipo=TipoReporte.INDICADORES,
            nombre="Reporte de Indicadores",
            descripcion="Análisis del estado actual de indicadores estratégicos con métricas avanzadas",
            tiempo_estimado="2-3 minutos",
            opciones_disponibles=[
                "Filtro por indicadores específicos",
                "Análisis temporal de tendencias",
                "Gráficos de semáforo avanzados",
                "Correlaciones entre indicadores",
                "Recomendaciones automáticas"
            ]
        ),
        TipoReporteInfo(
            tipo=TipoReporte.PROSPECTIVA,
            nombre="Reporte de Prospectiva",
            descripcion="Análisis prospectivo territorial y sectorial con escenarios detallados",
            tiempo_estimado="4-6 minutos",
            opciones_disponibles=[
                "Escenarios probabilísticos",
                "Análisis de factores de cambio",
                "Tendencias sectoriales",
                "Proyecciones temporales",
                "Matriz de impacto-probabilidad"
            ]
        ),
        TipoReporteInfo(
            tipo=TipoReporte.OFERTA_EDUCATIVA,
            nombre="Análisis de Oferta Educativa",
            descripcion="Estado actual y proyecciones de la oferta formativa con brechas identificadas",
            tiempo_estimado="3-4 minutos",
            opciones_disponibles=[
                "Análisis por sectores y regiones",
                "Identificación de brechas formativas",
                "Análisis de capacidad y ocupación",
                "Tendencias de demanda",
                "Proyecciones de crecimiento"
            ]
        ),
        TipoReporteInfo(
            tipo=TipoReporte.CONSOLIDADO,
            nombre="Reporte Estratégico Consolidado",
            descripcion="Reporte integral con todos los componentes y análisis cruzado",
            tiempo_estimado="8-12 minutos",
            opciones_disponibles=[
                "Resumen ejecutivo integrado",
                "Análisis DOFA completo",
                "Todos los indicadores y escenarios",
                "Correlaciones entre módulos",
                "Recomendaciones estratégicas",
                "Proyecciones ML (si disponible)"
            ]
        )
    ]

# -----------------------
# Generación (inicia background task)
# -----------------------
@router.post("/generar", response_model=ReporteResponse, status_code=status.HTTP_201_CREATED)
async def generar_reporte(
    solicitud: SolicitudReporte,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Inicia la generación de un reporte usando el nuevo sistema de recolección de datos.
    Usuario debe ser Planeación o Directivo/Administrador.
    """
    
    # Control de acceso
    allowed = ["planeacion", "superadmin", "administrativo", "directivos"]
    if not (hasattr(current_user, "role") and current_user.role in allowed) and not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="No tienes permisos para generar reportes")

    try:
        usuario_id = current_user.id

        # Crear registro del reporte
        nuevo_reporte = Reporte(
            tipo=solicitud.tipo.value,
            usuario_id=usuario_id,
            parametros=serialize_any(
                solicitud.parametros.dict() if hasattr(solicitud.parametros, "dict") 
                else solicitud.parametros
            ),
            estado="generando",
            fecha_generacion=datetime.utcnow()
        )
        db.add(nuevo_reporte)
        db.commit()
        db.refresh(nuevo_reporte)

        # Log de auditoría
        try:
            AuditLogger.log_user_action(
                db=db,
                action=AuditAction.REPORTE_GENERACION_INICIADA,
                user_id=current_user.id,
                user_email=getattr(current_user, "email", None),
                resource_type="REPORTE",
                resource_id=str(nuevo_reporte.id)
            )
        except Exception:
            logger.exception("No se pudo registrar la acción en AuditLogger")

        # Usar el nuevo servicio mejorado
        report_service = ImprovedReportService(db)

        # Iniciar tarea en background
        background_tasks.add_task(
            report_service.generar_reporte_background,
            nuevo_reporte.id,
            solicitud.tipo,
            solicitud.parametros,
            current_user.id
        )

        logger.info(f"Reporte {nuevo_reporte.id} iniciado para usuario {usuario_id}")

        return ReporteResponse.from_orm(nuevo_reporte)

    except Exception as e:
        logger.exception("Error al crear/iniciar la generación del reporte")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# -----------------------
# Estado y progreso de reporte
# -----------------------
@router.get("/status/{reporte_id}")
async def estado_reporte(
    reporte_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Devuelve el estado detallado del reporte con progreso y estadísticas
    """
    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    # Permisos: propietario o admin
    if reporte.usuario_id != current_user.id and not getattr(current_user, "is_admin", False) and current_user.role not in ("superadmin", "administrativo", "directivos"):
        raise HTTPException(status_code=403, detail="No tienes permisos para ver el estado de este reporte")

    # Usar servicio mejorado para obtener progreso detallado
    report_service = ImprovedReportService(db)
    progreso_detallado = report_service.obtener_progreso_reporte(reporte_id)

    return {
        "id": reporte.id,
        "estado": reporte.estado,
        "fecha_generacion": reporte.fecha_generacion,
        "archivo_nombre": reporte.archivo_nombre,
        "archivo_disponible": progreso_detallado.get("archivo_disponible", False),
        "tamaño_archivo": getattr(reporte, 'tamaño_archivo', None),
        "mensaje_error": progreso_detallado.get("mensaje_error"),
        "progreso_estimado": progreso_detallado.get("progreso_estimado", 0),
        "estadisticas_generacion": progreso_detallado.get("estadisticas", {}),
        "tiempo_transcurrido": _calculate_elapsed_time(reporte.fecha_generacion)  # ✅ corregido
    }


# -----------------------
# Validación previa de datos
# -----------------------
@router.post("/validar-datos")
async def validar_datos_reporte(
    solicitud: SolicitudReporte,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Valida que hay datos suficientes para generar el reporte solicitado
    """
    try:
        # Inicializar colector de datos
        data_collector = IntegratedDataCollectorService(db)
        
        # Verificar disponibilidad de datos
        resumen_sistema = data_collector.get_system_health_summary()
        
        # Realizar validación específica por tipo
        validacion = await _validar_datos_por_tipo(
            solicitud.tipo, 
            solicitud.parametros, 
            data_collector
        )
        
        return {
            "valido": validacion["valido"],
            "advertencias": validacion.get("advertencias", []),
            "errores": validacion.get("errores", []),
            "recomendaciones": validacion.get("recomendaciones", []),
            "resumen_sistema": resumen_sistema,
            "tiempo_estimado": _estimar_tiempo_generacion(solicitud.tipo, validacion)
        }
        
    except Exception as e:
        logger.error(f"Error en validación de datos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en validación: {str(e)}")

async def _validar_datos_por_tipo(
    tipo: TipoReporte, 
    parametros, 
    data_collector: IntegratedDataCollectorService
) -> dict:
    """Validación específica por tipo de reporte"""
    
    if tipo == TipoReporte.INDICADORES:
        # Verificar que hay indicadores activos
        indicadores_summary = data_collector.collectors["indicadores"].get_data_summary()
        total_indicadores = indicadores_summary.get("total_indicadores_activos", 0)
        
        if total_indicadores == 0:
            return {
                "valido": False,
                "errores": ["No hay indicadores activos en el sistema"],
                "recomendaciones": ["Agregar indicadores antes de generar el reporte"]
            }
        elif total_indicadores < 3:
            return {
                "valido": True,
                "advertencias": ["Pocos indicadores disponibles para análisis completo"],
                "recomendaciones": ["Considerar agregar más indicadores para mejor análisis"]
            }
        else:
            return {"valido": True}
    
    elif tipo == TipoReporte.DOFA:
        dofa_summary = data_collector.collectors["dofa"].get_data_summary()
        total_items = dofa_summary.get("total_items_dofa", 0)
        
        if total_items == 0:
            return {
                "valido": False,
                "errores": ["No hay elementos DOFA en el sistema"],
                "recomendaciones": ["Realizar análisis DOFA antes de generar el reporte"]
            }
        elif total_items < 8:  # Al menos 2 por categoría
            return {
                "valido": True,
                "advertencias": ["Pocos elementos DOFA para análisis robusto"],
                "recomendaciones": ["Agregar más elementos en cada categoría DOFA"]
            }
        else:
            return {"valido": True}
    
    elif tipo == TipoReporte.PROSPECTIVA:
        prospectiva_summary = data_collector.collectors["prospectiva"].get_data_summary()
        total_escenarios = prospectiva_summary.get("total_escenarios_activos", 0)
        
        if total_escenarios == 0:
            return {
                "valido": False,
                "errores": ["No hay escenarios prospectivos definidos"],
                "recomendaciones": ["Crear al menos un escenario prospectivo"]
            }
        else:
            return {"valido": True}
    
    elif tipo == TipoReporte.OFERTA_EDUCATIVA:
        oferta_summary = data_collector.collectors["oferta_educativa"].get_data_summary()
        total_programas = oferta_summary.get("total_programas_activos", 0)
        
        if total_programas == 0:
            return {
                "valido": False,
                "errores": ["No hay programas educativos activos"],
                "recomendaciones": ["Activar programas educativos antes de generar el reporte"]
            }
        else:
            return {"valido": True}
    
    elif tipo == TipoReporte.CONSOLIDADO:
        # Verificar múltiples módulos
        validaciones = {}
        for modulo in ["indicadores", "dofa", "prospectiva", "oferta_educativa"]:
            summary = data_collector.collectors[modulo].get_data_summary()
            validaciones[modulo] = summary
        
        modulos_sin_datos = []
        if validaciones["indicadores"].get("total_indicadores_activos", 0) == 0:
            modulos_sin_datos.append("Indicadores")
        if validaciones["dofa"].get("total_items_dofa", 0) == 0:
            modulos_sin_datos.append("DOFA")
        if validaciones["prospectiva"].get("total_escenarios_activos", 0) == 0:
            modulos_sin_datos.append("Prospectiva")
        if validaciones["oferta_educativa"].get("total_programas_activos", 0) == 0:
            modulos_sin_datos.append("Oferta Educativa")
        
        if len(modulos_sin_datos) >= 3:  # Máximo 1 módulo sin datos
            return {
                "valido": False,
                "errores": [f"Módulos sin datos suficientes: {', '.join(modulos_sin_datos)}"],
                "recomendaciones": ["Agregar datos en los módulos faltantes"]
            }
        elif len(modulos_sin_datos) > 0:
            return {
                "valido": True,
                "advertencias": [f"Módulos con pocos datos: {', '.join(modulos_sin_datos)}"],
                "recomendaciones": ["Considerar completar datos en módulos faltantes"]
            }
        else:
            return {"valido": True}
    
    return {"valido": True}

def _estimar_tiempo_generacion(tipo: TipoReporte, validacion: dict) -> str:
    """Estima tiempo de generación basado en tipo y validación"""
    tiempos_base = {
        TipoReporte.INDICADORES: 120,  # 2 minutos
        TipoReporte.DOFA: 90,          # 1.5 minutos
        TipoReporte.PROSPECTIVA: 300,  # 5 minutos
        TipoReporte.OFERTA_EDUCATIVA: 180,  # 3 minutos
        TipoReporte.CONSOLIDADO: 600   # 10 minutos
    }
    
    tiempo_base = tiempos_base.get(tipo, 180)
    
    # Ajustar por advertencias/errores
    if not validacion.get("valido", True):
        tiempo_base = 30  # Tiempo mínimo si hay errores
    elif validacion.get("advertencias"):
        tiempo_base = int(tiempo_base * 0.8)  # Reduce tiempo si hay pocos datos
    
    minutos = tiempo_base // 60
    segundos = tiempo_base % 60
    
    if minutos > 0:
        return f"{minutos}:{segundos:02d} minutos"
    else:
        return f"{segundos} segundos"

def _calculate_elapsed_time(fecha_inicio: datetime) -> str:
    """Calcula tiempo transcurrido desde inicio"""
    if not fecha_inicio:
        return "N/A"
    
    transcurrido = datetime.utcnow() - fecha_inicio
    total_segundos = int(transcurrido.total_seconds())
    
    if total_segundos < 60:
        return f"{total_segundos} segundos"
    elif total_segundos < 3600:
        minutos = total_segundos // 60
        segundos = total_segundos % 60
        return f"{minutos}:{segundos:02d}"
    else:
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        return f"{horas}:{minutos:02d} horas"

# -----------------------
# Listar reportes (propios / admin)
# -----------------------
@router.get("/", response_model=List[ReporteResponse])
async def listar_reportes(
    skip: int = 0,
    limit: int = 100,
    admin_view: bool = False,
    tipo: Optional[str] = Query(None, description="Filtrar por tipo de reporte"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    fecha_desde: Optional[datetime] = Query(None, description="Filtrar desde fecha"),
    fecha_hasta: Optional[datetime] = Query(None, description="Filtrar hasta fecha"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Lista reportes con filtros avanzados"""
    
    query = db.query(Reporte)

    # Control de acceso
    if admin_view:
        if not getattr(current_user, "is_admin", False) and current_user.role not in ("superadmin", "administrativo"):
            raise HTTPException(status_code=403, detail="Solo administradores pueden ver todos los reportes")
    else:
        query = query.filter(Reporte.usuario_id == current_user.id)

    # Aplicar filtros
    if tipo:
        query = query.filter(Reporte.tipo == tipo)
    if estado:
        query = query.filter(Reporte.estado == estado)
    if fecha_desde:
        query = query.filter(Reporte.fecha_generacion >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Reporte.fecha_generacion <= fecha_hasta)

    # Obtener resultados
    reportes = query.order_by(Reporte.fecha_generacion.desc()).offset(skip).limit(limit).all()
    
    # Enriquecer con estadísticas
    reportes_enriquecidos = []
    for reporte in reportes:
        reporte_data = ReporteResponse.from_orm(reporte)
        
        # Agregar estadísticas adicionales si están disponibles
        if hasattr(reporte, 'estadisticas_generacion') and reporte.estadisticas_generacion:
            reporte_data.estadisticas = reporte.estadisticas_generacion
        
        reportes_enriquecidos.append(reporte_data)
    
    return reportes_enriquecidos

# -----------------------
# Estadísticas del sistema de reportes
# -----------------------
@router.get("/estadisticas/sistema")
async def estadisticas_sistema(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Obtiene estadísticas generales del sistema de reportes"""
    
    # Requiere permisos administrativos
    if not getattr(current_user, "is_admin", False) and current_user.role not in ("superadmin", "administrativo", "directivos"):
        raise HTTPException(status_code=403, detail="No tienes permisos para ver estadísticas del sistema")
    
    try:
        # Estadísticas básicas
        total_reportes = db.query(Reporte).count()
        reportes_ultimo_mes = db.query(Reporte).filter(
            Reporte.fecha_generacion >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        # Por estado
        por_estado = db.query(Reporte.estado, func.count(Reporte.id)).group_by(Reporte.estado).all()
        
        # Por tipo
        por_tipo = db.query(Reporte.tipo, func.count(Reporte.id)).group_by(Reporte.tipo).all()
        
        # Usuarios más activos
        usuarios_activos = db.query(
            Reporte.usuario_id, 
            func.count(Reporte.id).label('total_reportes')
        ).group_by(Reporte.usuario_id).order_by(desc('total_reportes')).limit(10).all()
        
        # Estado de salud del sistema de datos
        data_collector = IntegratedDataCollectorService(db)
        salud_sistema = data_collector.get_system_health_summary()
        
        return {
            "estadisticas_generales": {
                "total_reportes": total_reportes,
                "reportes_ultimo_mes": reportes_ultimo_mes,
                "por_estado": dict(por_estado),
                "por_tipo": dict(por_tipo)
            },
            "usuarios_activos": [
                {"usuario_id": user_id, "total_reportes": total}
                for user_id, total in usuarios_activos
            ],
            "salud_sistema_datos": salud_sistema,
            "ultima_actualizacion": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del sistema: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")

# -----------------------
# Endpoints existentes (mantener compatibilidad)
# -----------------------
@router.get("/mis-reportes", response_model=List[ReporteResponse])
async def mis_reportes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
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
    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    if reporte.usuario_id != current_user.id and not getattr(current_user, "is_admin", False) and current_user.role not in ("superadmin", "administrativo", "directivos"):
        raise HTTPException(status_code=403, detail="No tienes permisos para ver este reporte")

    return ReporteResponse.from_orm(reporte)

@router.get("/indicadores/", response_model=List[IndicadorResponse])
async def obtener_indicadores(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Obtiene lista de indicadores disponibles usando el nuevo colector"""
    try:
        data_collector = IntegratedDataCollectorService(db)
        indicadores_data = data_collector.collectors["indicadores"].collect_data(None)
        
        return indicadores_data.get("indicadores", [])
        
    except Exception as e:
        logger.error(f"Error obteniendo indicadores: {str(e)}")
        raise HTTPException(status_code=500, detail="Error obteniendo indicadores")

# -----------------------
# Descargar / Ver / Eliminar (mantener funcionalidad existente)
# -----------------------
@router.get("/{reporte_id}/descargar")
async def descargar_reporte(
    reporte_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    # Verificar permisos
    if reporte.usuario_id != current_user.id:
        if not getattr(current_user, "is_admin", False) and current_user.role not in ['superadmin', 'administrativo', 'directivos']:
            raise HTTPException(status_code=403, detail="No tienes permisos para descargar este reporte")

    # Registrar descarga en auditoría
    try:
        AuditLogger.log_user_action(
            db=db,
            action=AuditAction.REPORTE_DESCARGA,
            user_id=current_user.id,
            user_email=getattr(current_user, "email", None),
            resource_type="REPORTE",
            resource_id=str(reporte.id)
        )
    except Exception:
        logger.exception("No se pudo registrar descarga en auditoría")

    # Preferir contenido en BD
    if reporte.archivo_contenido:
        return _serve_binary_pdf(reporte.archivo_contenido, reporte.archivo_nombre or f"reporte_{reporte.id}.pdf", inline=False)
    
    # Fallback filesystem
    elif reporte.archivo_path and os.path.exists(reporte.archivo_path):
        filename = reporte.archivo_nombre or f"reporte_{reporte.id}.pdf"
        return FileResponse(
            path=reporte.archivo_path,
            filename=_sanitize_filename(filename),
            media_type="application/pdf"
        )
    else:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

@router.get("/{reporte_id}/ver")
async def ver_reporte(
    reporte_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    if reporte.usuario_id != current_user.id:
        if not getattr(current_user, "is_admin", False) and current_user.role not in ['superadmin', 'administrativo', 'directivos']:
            raise HTTPException(status_code=403, detail="No tienes permisos para ver este reporte")

    if reporte.archivo_contenido:
        return _serve_binary_pdf(reporte.archivo_contenido, reporte.archivo_nombre or f"reporte_{reporte.id}.pdf", inline=True)
    elif reporte.archivo_path and os.path.exists(reporte.archivo_path):
        with open(reporte.archivo_path, "rb") as f:
            content = f.read()
        return _serve_binary_pdf(content, reporte.archivo_nombre or f"reporte_{reporte.id}.pdf", inline=True)
    else:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

@router.delete("/{reporte_id}")
async def eliminar_reporte(
    reporte_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    if reporte.usuario_id != current_user.id and not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="No tienes permisos para eliminar este reporte")

    # Eliminar archivo físico si existe
    if reporte.archivo_path and os.path.exists(reporte.archivo_path):
        try:
            os.remove(reporte.archivo_path)
            logger.info(f"Archivo eliminado: {reporte.archivo_path}")
        except Exception:
            logger.exception("No se pudo eliminar archivo físico")

    db.delete(reporte)
    db.commit()

    try:
        AuditLogger.log_user_action(
            db=db,
            action=AuditAction.REPORTE_ELIMINADO,
            user_id=current_user.id,
            user_email=getattr(current_user, "email", None),
            resource_type="REPORTE",
            resource_id=str(reporte_id)
        )
    except Exception:
        logger.exception("No se pudo registrar en auditoría la eliminación")

    return JSONResponse({"message": "Reporte eliminado exitosamente"})

# -----------------------
# Admin: listar todos (solo admins)
# -----------------------
@router.get("/admin/todos", response_model=List[ReporteResponse])
async def listar_todos_reportes_admin(
    skip: int = 0,
    limit: int = 100,
    usuario_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    if not getattr(current_user, "is_admin", False) and current_user.role not in ("superadmin", "administrativo"):
        raise HTTPException(status_code=403, detail="Solo administradores pueden acceder")

    query = db.query(Reporte)
    if usuario_id:
        query = query.filter(Reporte.usuario_id == usuario_id)

    reportes = query.order_by(Reporte.fecha_generacion.desc()).offset(skip).limit(limit).all()
    return [ReporteResponse.from_orm(reporte) for reporte in reportes]