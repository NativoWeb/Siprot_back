from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import DemandIndicator
from schemas import DemandIndicatorCreate
from routers.auth import require_role
from models import Document

router = APIRouter(prefix="/demand-indicators", tags=["Demand Indicators"])

@router.post("/", response_model=DemandIndicatorCreate)
def create_demand_indicator(
    data: DemandIndicatorCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["planeacion"]))
):
    # Verificar documento solo si lo mandan
    if data.source_document_id:
        doc = db.query(Document).filter(Document.id == data.source_document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")

    new = DemandIndicator(
        sector=data.sector,
        year=data.year,
        demand_value=data.demand_value,
        indicator_value=data.indicator_value,
        source_document_id=data.source_document_id
    )

    db.add(new)
    db.commit()
    db.refresh(new)
    return new



