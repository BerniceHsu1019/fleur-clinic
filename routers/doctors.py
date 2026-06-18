from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models import Doctor

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


@router.get("")
def list_doctors(
    service: Optional[str] = Query(None),  # NHI | GROWTH | MENTAL
    db: Session = Depends(get_db),
):
    q = db.query(Doctor).filter(Doctor.is_active == True)
    if service == "NHI":
        q = q.filter(Doctor.supports_nhi == True)
    elif service == "GROWTH":
        q = q.filter(Doctor.supports_growth == True)
    elif service == "MENTAL":
        q = q.filter(Doctor.supports_mental == True)
    doctors = q.all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "title": d.title,
            "specialty": d.specialty,
            "supports_nhi": d.supports_nhi,
            "supports_growth": d.supports_growth,
            "supports_mental": d.supports_mental,
        }
        for d in doctors
    ]
