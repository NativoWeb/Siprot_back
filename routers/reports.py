from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import Response, FileResponse, JSONResponse
from sqlalchemy.orm import Session
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
from services.report_service import ReportService
from services.data_service import DataService

# Auth / permisos (ajusta import si tus nombres son diferentes)
from routers.auth import get_current_user, require_role
from routers.audit import AuditLogger, AuditAction  # Usa tu AuditLogger

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
    # reemplaza espacios por guiones bajos y elimina caracteres peligrosos
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
    Inicia la generación de un reporte. Usuario debe ser Planeación o Directivo/Administrador.
    Genera un registro Reporte con estado "generando" y dispara la tarea en background.
    """

    # Control de acceso: solo planeacion o directivos/administrativos/superadmin
    allowed = ["planeacion", "superadmin", "administrativo", "directivos"]
    if not (hasattr(current_user, "role") and current_user.role in allowed) and not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="No tienes permisos para generar reportes")

    try:
        usuario_id = current_user.id

        nuevo_reporte = Reporte(
            tipo=solicitud.tipo.value,
            usuario_id=usuario_id,
            parametros=serialize_any(solicitud.parametros.dict() if hasattr(solicitud.parametros, "dict") else solicitud.parametros),
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

        report_service = ReportService(db)

        # la función generar_reporte_background debe aceptar: reporte_id, tipo, parametros
        background_tasks.add_task(
            report_service.generar_reporte_background,
            nuevo_reporte.id,
            solicitud.tipo,
            solicitud.parametros
        )

        return ReporteResponse.from_orm(nuevo_reporte)

    except Exception as e:
        logger.exception("Error al crear/iniciar la generación del reporte")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# -----------------------
# Estado de un reporte
# -----------------------
@router.get("/status/{reporte_id}")
async def estado_reporte(
    reporte_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Devuelve el estado básico del reporte: generating, listo, error, etc.
    """

    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    # Permisos: propietario o admin
    if reporte.usuario_id != current_user.id and not getattr(current_user, "is_admin", False) and current_user.role not in ("superadmin", "administrativo", "directivos"):
        raise HTTPException(status_code=403, detail="No tienes permisos para ver el estado de este reporte")

    return {
        "id": reporte.id,
        "estado": reporte.estado,
        "fecha_generacion": reporte.fecha_generacion,
        "archivo_nombre": reporte.archivo_nombre,
        "archivo_path": bool(reporte.archivo_path),
        "en_bd": bool(reporte.archivo_contenido)
    }


# -----------------------
# Listar reportes (propios / admin)
# -----------------------
@router.get("/", response_model=List[ReporteResponse])
async def listar_reportes(
    skip: int = 0,
    limit: int = 100,
    admin_view: bool = False,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(Reporte)

    # Si admin_view true, garantizar permisos de admin
    if admin_view:
        if not getattr(current_user, "is_admin", False) and current_user.role not in ("superadmin", "administrativo"):
            raise HTTPException(status_code=403, detail="Solo administradores pueden ver todos los reportes")
    else:
        query = query.filter(Reporte.usuario_id == current_user.id)

    reportes = query.order_by(Reporte.fecha_generacion.desc()).offset(skip).limit(limit).all()
    return [ReporteResponse.from_orm(r) for r in reportes]


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


# -----------------------
# Obtener indicadores
# -----------------------
@router.get("/indicadores/", response_model=List[IndicadorResponse])
async def obtener_indicadores(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    data_service = DataService(db)
    return data_service.obtener_indicadores()


# -----------------------
# Descargar / Ver / Eliminar
# -----------------------
def _maybe_schedule_file_cleanup(background_tasks: BackgroundTasks, path: str, delay_seconds: int = 10):
    """Programa la eliminación del archivo en filesystem tras cierto delay (si se desea)."""
    def _del(path_to_rm):
        try:
            if os.path.exists(path_to_rm):
                os.remove(path_to_rm)
                logger.info(f"Archivo temporal eliminado: {path_to_rm}")
        except Exception:
            logger.exception("Error eliminando archivo temporal")

    # Programar tarea simple: la API BackgroundTasks ejecuta la función al finalizar la respuesta
    background_tasks.add_task(_del, path)


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

    # Verificar permisos: propietario o roles administrativos
    if reporte.usuario_id != current_user.id:
        if not getattr(current_user, "is_admin", False) and current_user.role not in ['superadmin', 'administrativo', 'directivos']:
            raise HTTPException(status_code=403, detail="No tienes permisos para descargar este reporte")

    # Preferir contenido en BD
    if reporte.archivo_contenido:
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

        return _serve_binary_pdf(reporte.archivo_contenido, reporte.archivo_nombre or f"reporte_{reporte.id}.pdf", inline=False)

    # Fallback filesystem
    elif reporte.archivo_path and os.path.exists(reporte.archivo_path):
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

        # servir con FileResponse (streaming eficiente)
        filename = reporte.archivo_nombre or f"reporte_{reporte.id}.pdf"

        # Podemos programar la eliminación del archivo si es temporal
        # background_tasks.add_task(os.remove, reporte.archivo_path)  # opcional
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
        # Leer y retornar contenido (considerar streaming si archivos grandes)
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
