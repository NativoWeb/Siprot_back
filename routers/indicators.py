# routers/indicators.py
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from database import get_db
from models import Indicador
from schemas import IndicadorCreate, IndicadorResponse, ResumenIndicadores, IndicadorUpdate
from routers.auth import require_role
from typing import List, Optional
from datetime import datetime, timedelta
import io
import csv
import pandas as pd

router = APIRouter(
    prefix="/indicators",
    tags=["Indicadores Estratégicos"]
)

# ================= FUNCIONES AUXILIARES =================

def calcular_estado_semaforo(valor_actual: float, meta: float) -> str:
    """Calcula el estado del semáforo basado en el cumplimiento"""
    if meta <= 0:
        return "rojo"
    
    cumplimiento = (valor_actual / meta * 100)
    
    if cumplimiento >= 100:
        return "verde"
    elif cumplimiento >= 70:
        return "amarillo"
    else:
        return "rojo"

def calcular_cumplimiento(valor_actual: float, meta: float) -> float:
    """Calcula el porcentaje de cumplimiento"""
    if meta <= 0:
        return 0.0
    return (valor_actual / meta * 100)

def convertir_a_response(indicador: Indicador) -> IndicadorResponse:
    """Convierte un modelo Indicador a IndicadorResponse"""
    cumplimiento = calcular_cumplimiento(indicador.valor_actual, indicador.meta)
    estado = calcular_estado_semaforo(indicador.valor_actual, indicador.meta)
    
    return IndicadorResponse(
        id=indicador.id,
        nombre=indicador.nombre,
        valor_actual=indicador.valor_actual,
        meta=indicador.meta,
        unidad=indicador.unidad,
        tendencia=indicador.tendencia,
        descripcion=indicador.descripcion,
        categoria=indicador.categoria,
        fecha_actualizacion=indicador.fecha_actualizacion,
        cumplimiento=cumplimiento,
        estado_semaforo=estado
    )

# ================= CRUD =================

@router.post("/", response_model=IndicadorResponse)
def crear_indicador(
    indicador: IndicadorCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["planeacion", "superadmin"]))
):
    """
    Crea un nuevo indicador estratégico
    
    Requiere rol: planeacion o superadmin
    """
    nuevo = Indicador(
        nombre=indicador.nombre,
        valor_actual=indicador.valor_actual,
        meta=indicador.meta,
        unidad=indicador.unidad,
        tendencia=indicador.tendencia,
        descripcion=indicador.descripcion,
        categoria=indicador.categoria,
        fecha_actualizacion=datetime.utcnow(),
        valores_historicos=[{
            "fecha": str(datetime.utcnow().date()), 
            "valor": indicador.valor_actual
        }],
        metas_historicas=[{
            "fecha": str(datetime.utcnow().date()), 
            "meta": indicador.meta
        }]
    )
    
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    
    return convertir_a_response(nuevo)


@router.get("/", response_model=List[IndicadorResponse])
def listar_indicadores(
    categoria: Optional[str] = Query(None, description="Filtrar por categoría"),
    estado: Optional[str] = Query(None, description="Filtrar por estado semáforo"),
    fecha_desde: Optional[str] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[str] = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    user=Depends(require_role(["directivos", "planeacion", "superadmin"]))
):
    """
    Lista todos los indicadores activos con filtros opcionales
    
    Requiere rol: directivos, planeacion o superadmin
    """
    query = db.query(Indicador).filter(Indicador.activo == True)
    
    # Aplicar filtros
    if categoria:
        query = query.filter(Indicador.categoria == categoria)
    
    if fecha_desde:
        try:
            fecha_desde_dt = datetime.strptime(fecha_desde, "%Y-%m-%d")
            query = query.filter(Indicador.fecha_actualizacion >= fecha_desde_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha_desde inválido. Use YYYY-MM-DD")
    
    if fecha_hasta:
        try:
            fecha_hasta_dt = datetime.strptime(fecha_hasta, "%Y-%m-%d")
            # Agregar un día para incluir todo el día especificado
            fecha_hasta_dt = fecha_hasta_dt + timedelta(days=1)
            query = query.filter(Indicador.fecha_actualizacion < fecha_hasta_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha_hasta inválido. Use YYYY-MM-DD")
    
    indicadores = query.all()
    
    # Convertir a response y aplicar filtro de estado si es necesario
    respuestas = [convertir_a_response(ind) for ind in indicadores]
    
    if estado:
        respuestas = [r for r in respuestas if r.estado_semaforo == estado]
    
    return respuestas


# ================= Resumen =================

@router.get("/resumen", response_model=ResumenIndicadores)
def resumen_indicadores(
    db: Session = Depends(get_db),
    user=Depends(require_role(["directivos", "planeacion", "superadmin"]))
):
    """
    Obtiene un resumen ejecutivo de todos los indicadores
    
    Requiere rol: directivos, planeacion o superadmin
    """
    indicadores = db.query(Indicador).filter(Indicador.activo == True).all()
    total = len(indicadores)
    verde = amarillo = rojo = 0
    suma_cumplimiento = 0

    for ind in indicadores:
        cumplimiento = calcular_cumplimiento(ind.valor_actual, ind.meta)
        suma_cumplimiento += cumplimiento
        
        estado = calcular_estado_semaforo(ind.valor_actual, ind.meta)
        if estado == "verde":
            verde += 1
        elif estado == "amarillo":
            amarillo += 1
        else:
            rojo += 1

    cumplimiento_general = (suma_cumplimiento / total) if total > 0 else 0

    return ResumenIndicadores(
        total_indicadores=total,
        verde=verde,
        amarillo=amarillo,
        rojo=rojo,
        cumplimiento_general=cumplimiento_general
    )


# ================= Operaciones por ID =================

@router.get("/{indicador_id}", response_model=IndicadorResponse)
def obtener_indicador(
    indicador_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(["directivos", "planeacion", "superadmin"]))
):
    """
    Obtiene un indicador específico por ID
    
    Requiere rol: directivos, planeacion o superadmin
    """
    ind = db.query(Indicador).filter(
        Indicador.id == indicador_id,
        Indicador.activo == True
    ).first()
    
    if not ind:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    return convertir_a_response(ind)


@router.put("/", response_model=IndicadorResponse)
def actualizar_indicador(
    data: IndicadorUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["planeacion", "superadmin"]))
):
    """
    Actualiza un indicador existente
    
    Requiere rol: planeacion o superadmin
    """
    ind = db.query(Indicador).filter(Indicador.id == data.id).first()
    if not ind:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    # Actualizar campos
    ind.nombre = data.nombre
    ind.descripcion = data.descripcion
    ind.valor_actual = data.valor_actual
    ind.meta = data.meta
    ind.unidad = data.unidad
    ind.categoria = data.categoria
    ind.tendencia = data.tendencia
    ind.fecha_actualizacion = datetime.utcnow()

    # Guardar históricos
    fecha_actual = str(datetime.utcnow().date())
    
    if not ind.valores_historicos:
        ind.valores_historicos = []
    
    # Evitar duplicados del mismo día
    if not any(h.get('fecha') == fecha_actual for h in ind.valores_historicos):
        ind.valores_historicos.append({
            "fecha": fecha_actual, 
            "valor": data.valor_actual
        })

    if not ind.metas_historicas:
        ind.metas_historicas = []
    
    if not any(m.get('fecha') == fecha_actual for m in ind.metas_historicas):
        ind.metas_historicas.append({
            "fecha": fecha_actual, 
            "meta": data.meta
        })

    db.commit()
    db.refresh(ind)

    return convertir_a_response(ind)


@router.delete("/{indicador_id}")
def eliminar_indicador(
    indicador_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(["planeacion", "superadmin"]))
):
    """
    Elimina (desactiva) un indicador
    
    Requiere rol: planeacion o superadmin
    """
    ind = db.query(Indicador).filter(Indicador.id == indicador_id).first()
    if not ind:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    ind.activo = False
    db.commit()
    
    return {"message": "Indicador eliminado correctamente", "id": indicador_id}


# ================= Históricos =================

@router.get("/{indicador_id}/history")
def historial_indicador(
    indicador_id: int,
    years: int = Query(5, ge=1, le=20, description="Años de histórico a obtener"),
    db: Session = Depends(get_db),
    user=Depends(require_role(["directivos", "planeacion", "superadmin"]))
):
    """
    Obtiene el histórico de valores y metas de un indicador
    
    Requiere rol: directivos, planeacion o superadmin
    """
    ind = db.query(Indicador).filter(
        Indicador.id == indicador_id,
        Indicador.activo == True
    ).first()
    
    if not ind:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    # Obtener históricos limitados por años
    historicos = (ind.valores_historicos or [])
    metas = (ind.metas_historicas or [])
    
    # Calcular fecha límite
    fecha_limite = datetime.utcnow() - timedelta(days=365 * years)
    fecha_limite_str = str(fecha_limite.date())
    
    # Filtrar por fecha
    historicos_filtrados = [
        h for h in historicos 
        if h.get('fecha', '9999-99-99') >= fecha_limite_str
    ]
    
    metas_filtradas = [
        m for m in metas 
        if m.get('fecha', '9999-99-99') >= fecha_limite_str
    ]
    
    # Ordenar por fecha
    historicos_filtrados.sort(key=lambda x: x.get('fecha', ''))
    metas_filtradas.sort(key=lambda x: x.get('fecha', ''))

    return {
        "id": ind.id,
        "nombre": ind.nombre,
        "unidad": ind.unidad,
        "historicos": historicos_filtrados,
        "metas": metas_filtradas,
        "years_requested": years
    }


# ================= Exportación =================

@router.get("/export")
def exportar_indicadores(
    format: str = Query("csv", regex="^(csv|excel)$", description="Formato de exportación"),
    categoria: Optional[str] = Query(None, description="Filtrar por categoría"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    db: Session = Depends(get_db),
    user=Depends(require_role(["directivos", "planeacion", "superadmin"]))
):
    """
    Exporta los indicadores a CSV o Excel
    
    Requiere rol: directivos, planeacion o superadmin
    """
    query = db.query(Indicador).filter(Indicador.activo == True)
    
    # Aplicar filtros
    if categoria:
        query = query.filter(Indicador.categoria == categoria)
    
    indicadores = query.all()
    
    # Convertir a responses para aplicar filtro de estado
    responses = [convertir_a_response(ind) for ind in indicadores]
    
    if estado:
        responses = [r for r in responses if r.estado_semaforo == estado]

    if not responses:
        return Response(
            content="No hay datos para exportar",
            media_type="text/plain",
            status_code=404
        )

    # Preparar datos
    data = []
    for resp in responses:
        data.append({
            "ID": resp.id,
            "Nombre": resp.nombre,
            "Descripción": resp.descripcion or "",
            "Valor Actual": resp.valor_actual,
            "Meta": resp.meta,
            "Unidad": resp.unidad,
            "Cumplimiento (%)": round(resp.cumplimiento, 2),
            "Estado": resp.estado_semaforo,
            "Tendencia": resp.tendencia,
            "Categoría": resp.categoria,
            "Fecha Actualización": resp.fecha_actualizacion.strftime("%Y-%m-%d %H:%M:%S") if resp.fecha_actualizacion else ""
        })

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=indicadores_estrategicos.csv",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )
    else:  # excel
        df = pd.DataFrame(data)
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Indicadores")
            
            # Ajustar ancho de columnas
            worksheet = writer.sheets["Indicadores"]
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                ) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)
        
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=indicadores_estrategicos.xlsx"
            }
        )


# ================= Estadísticas Adicionales =================

@router.get("/stats/categorias")
def estadisticas_por_categoria(
    db: Session = Depends(get_db),
    user=Depends(require_role(["directivos", "planeacion", "superadmin"]))
):
    """
    Obtiene estadísticas agrupadas por categoría
    
    Requiere rol: directivos, planeacion o superadmin
    """
    indicadores = db.query(Indicador).filter(Indicador.activo == True).all()
    
    stats_por_categoria = {}
    
    for ind in indicadores:
        cat = ind.categoria or "Sin categoría"
        
        if cat not in stats_por_categoria:
            stats_por_categoria[cat] = {
                "categoria": cat,
                "total": 0,
                "verde": 0,
                "amarillo": 0,
                "rojo": 0,
                "cumplimiento_promedio": 0,
                "suma_cumplimiento": 0
            }
        
        stats = stats_por_categoria[cat]
        stats["total"] += 1
        
        cumplimiento = calcular_cumplimiento(ind.valor_actual, ind.meta)
        stats["suma_cumplimiento"] += cumplimiento
        
        estado = calcular_estado_semaforo(ind.valor_actual, ind.meta)
        stats[estado] += 1
    
    # Calcular promedios
    resultado = []
    for cat, stats in stats_por_categoria.items():
        stats["cumplimiento_promedio"] = round(
            stats["suma_cumplimiento"] / stats["total"], 2
        ) if stats["total"] > 0 else 0
        del stats["suma_cumplimiento"]
        resultado.append(stats)
    
    return resultado