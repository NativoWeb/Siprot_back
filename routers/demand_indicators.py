from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import DemandIndicator
from schemas import DemandIndicatorCreate
from routers.auth import require_role

router = APIRouter(prefix="/demand-indicators", tags=["Demand Indicators"])

@router.post("/", response_model=DemandIndicatorCreate)
def create_demand_indicator(
    data: DemandIndicatorCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["planeacion"]))
):
    new = DemandIndicator(
        sector=data.sector,
        year=data.year,
        demand_value=data.demand_value,
        source=data.source,
        created_by=user.id
    )
    db.add(new)
    db.commit()
    db.refresh(new)
    return new
