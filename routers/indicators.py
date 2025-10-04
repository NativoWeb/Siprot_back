# routers/indicators.py
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from database import get_db
from models import Indicador
from schemas import IndicadorCreate, IndicadorResponse, ResumenIndicadores, IndicadorUpdate
from routers.auth import require_role
from typing import List
from datetime import datetime
import io
import csv
import pandas as pd

router = APIRouter(
    prefix="/indicators",
    tags=["Indicadores Estratégicos"]
)

# ================= CRUD =================

@router.post("/", response_model=IndicadorResponse)
def crear_indicador(
    indicador: IndicadorCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["planeacion", "superadmin"]))
):
    nuevo = Indicador(
        nombre=indicador.nombre,
        valor_actual=indicador.valor_actual,
        meta=indicador.meta,
        unidad=indicador.unidad,
        tendencia=indicador.tendencia,
        descripcion=indicador.descripcion,
        categoria=indicador.categoria,
        fecha_actualizacion=datetime.utcnow(),
        valores_historicos=[{"fecha": str(datetime.utcnow().date()), "valor": indicador.valor_actual}],
        metas_historicas=[{"fecha": str(datetime.utcnow().date()), "meta": indicador.meta}]
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.get("/", response_model=List[IndicadorResponse])
def listar_indicadores(
    db: Session = Depends(get_db),
    user=Depends(require_role(["directivos", "planeacion", "superadmin"]))
):
    indicadores = db.query(Indicador).filter(Indicador.activo == True).all()
    resp = []
    for ind in indicadores:
        cumplimiento = (ind.valor_actual / ind.meta * 100) if ind.meta > 0 else 0
        if cumplimiento >= 100:
            estado = "verde"
        elif cumplimiento >= 70:
            estado = "amarillo"
        else:
            estado = "rojo"
        resp.append(
            IndicadorResponse(
                id=ind.id,
                nombre=ind.nombre,
                valor_actual=ind.valor_actual,
                meta=ind.meta,
                unidad=ind.unidad,
                tendencia=ind.tendencia,
                descripcion=ind.descripcion,
                categoria=ind.categoria,
                fecha_actualizacion=ind.fecha_actualizacion,
                cumplimiento=cumplimiento,
                estado_semaforo=estado
            )
        )
    return resp

# ================= Resumen =================

@router.get("/resumen", response_model=ResumenIndicadores)
def resumen_indicadores(
    db: Session = Depends(get_db),
    user=Depends(require_role(["directivos", "planeacion", "superadmin"]))
):
    indicadores = db.query(Indicador).filter(Indicador.activo == True).all()
    total = len(indicadores)
    verde = amarillo = rojo = 0

    for ind in indicadores:
        cumplimiento = (ind.valor_actual / ind.meta * 100) if ind.meta > 0 else 0
        if cumplimiento >= 100:
            verde += 1
        elif cumplimiento >= 70:
            amarillo += 1
        else:
            rojo += 1

    cumplimiento_general = (verde / total * 100) if total > 0 else 0

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
    ind = db.query(Indicador).filter(Indicador.id == indicador_id).first()
    if not ind:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    cumplimiento = (ind.valor_actual / ind.meta * 100) if ind.meta > 0 else 0
    if cumplimiento >= 100:
        estado = "verde"
    elif cumplimiento >= 70:
        estado = "amarillo"
    else:
        estado = "rojo"

    return IndicadorResponse(
        id=ind.id,
        nombre=ind.nombre,
        valor_actual=ind.valor_actual,
        meta=ind.meta,
        unidad=ind.unidad,
        tendencia=ind.tendencia,
        descripcion=ind.descripcion,
        categoria=ind.categoria,
        fecha_actualizacion=ind.fecha_actualizacion,
        cumplimiento=cumplimiento,
        estado_semaforo=estado
    )


@router.put("/", response_model=IndicadorResponse)
def actualizar_indicador(
    data: IndicadorUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["planeacion", "superadmin"]))
):
    ind = db.query(Indicador).filter(Indicador.id == data.id).first()
    if not ind:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    ind.nombre = data.nombre
    ind.descripcion = data.descripcion
    ind.valor_actual = data.valor_actual
    ind.meta = data.meta
    ind.unidad = data.unidad
    ind.categoria = data.categoria
    ind.tendencia = data.tendencia
    ind.fecha_actualizacion = datetime.utcnow()

    # Guardar históricos
    if not ind.valores_historicos:
        ind.valores_historicos = []
    ind.valores_historicos.append({"fecha": str(datetime.utcnow().date()), "valor": data.valor_actual})

    if not ind.metas_historicas:
        ind.metas_historicas = []
    ind.metas_historicas.append({"fecha": str(datetime.utcnow().date()), "meta": data.meta})

    db.commit()
    db.refresh(ind)

    # Calcular cumplimiento y estado_semaforo
    cumplimiento = (ind.valor_actual / ind.meta * 100) if ind.meta > 0 else 0
    if cumplimiento >= 100:
        estado = "verde"
    elif cumplimiento >= 70:
        estado = "amarillo"
    else:
        estado = "rojo"

    return IndicadorResponse(
        id=ind.id,
        nombre=ind.nombre,
        valor_actual=ind.valor_actual,
        meta=ind.meta,
        unidad=ind.unidad,
        tendencia=ind.tendencia,
        descripcion=ind.descripcion,
        categoria=ind.categoria,
        fecha_actualizacion=ind.fecha_actualizacion,
        cumplimiento=cumplimiento,
        estado_semaforo=estado
    )

@router.delete("/{indicador_id}")
def eliminar_indicador(
    indicador_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(["planeacion", "superadmin"]))
):
    ind = db.query(Indicador).filter(Indicador.id == indicador_id).first()
    if not ind:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    ind.activo = False
    db.commit()
    return {"message": "Indicador eliminado correctamente"}

# ================= Históricos =================

@router.get("/{indicador_id}/history")
def historial_indicador(
    indicador_id: int,
    years: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user=Depends(require_role(["directivos", "planeacion", "superadmin"]))
):
    ind = db.query(Indicador).filter(Indicador.id == indicador_id).first()
    if not ind:
        raise HTTPException(status_code=404, detail="Indicador no encontrado")

    historicos = (ind.valores_historicos or [])[-years:]
    metas = (ind.metas_historicas or [])[-years:]

    return {
        "id": ind.id,
        "nombre": ind.nombre,
        "unidad": ind.unidad,
        "historicos": historicos,
        "metas": metas
    }

# ================= Exportación =================

@router.get("/export")
def exportar_indicadores(
    format: str = Query("csv", regex="^(csv|excel)$"),
    db: Session = Depends(get_db),
    user=Depends(require_role(["directivos", "planeacion", "superadmin"]))
):
    indicadores = db.query(Indicador).filter(Indicador.activo == True).all()

    data = []
    for ind in indicadores:
        data.append({
            "id": ind.id,
            "nombre": ind.nombre,
            "valor_actual": ind.valor_actual,
            "meta": ind.meta,
            "unidad": ind.unidad,
            "tendencia": ind.tendencia,
            "descripcion": ind.descripcion,
            "categoria": ind.categoria,
            "fecha_actualizacion": ind.fecha_actualizacion
        })

    if not data:
        return Response(content="", media_type="text/plain")

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=indicadores.csv"}
        )
    else:
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=indicadores.xlsx"}
        )
