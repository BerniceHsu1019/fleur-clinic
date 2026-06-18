from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models import Doctor, ClinicSession, Patient, Appointment

router = APIRouter(prefix="/api/admin", tags=["admin"])

APPOINTMENT_TYPE_LABELS = {
    "NHI": "健保",
    "PRIVATE_GROWTH": "自費－生長發育",
    "PRIVATE_MENTAL": "自費－兒童心智",
}

STATUS_LABELS = {
    "CONFIRMED": "已確認",
    "CANCELLED": "已取消",
    "COMPLETED": "已完診",
    "NO_SHOW": "未到診",
}

DAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"]


def _format_appointment(a: Appointment, db: Session) -> dict:
    doctor = db.query(Doctor).filter(Doctor.id == a.doctor_id).first()
    patient = db.query(Patient).filter(Patient.id == a.patient_id).first()
    return {
        "id": a.id,
        "date": a.date,
        "doctor_name": doctor.name if doctor else "",
        "doctor_title": doctor.title if doctor else "",
        "patient_name": patient.child_name or patient.name if patient else "",
        "guardian_name": patient.name if patient and patient.child_name else None,
        "phone": patient.phone if patient else "",
        "nhi_number": patient.nhi_number if patient else "",
        "appointment_type": a.appointment_type,
        "appointment_type_label": APPOINTMENT_TYPE_LABELS.get(a.appointment_type, a.appointment_type),
        "visit_type": a.visit_type,
        "queue_number": a.queue_number,
        "start_time": a.start_time,
        "end_time": a.end_time,
        "status": a.status,
        "status_label": STATUS_LABELS.get(a.status, a.status),
        "notes": a.notes,
        "his_synced": a.his_synced,
        "his_id": a.his_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/appointments")
def list_appointments(
    target_date: Optional[str] = Query(None),
    doctor_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    if target_date is None:
        target_date = date.today().isoformat()

    q = db.query(Appointment).filter(Appointment.date == target_date)
    if doctor_id:
        q = q.filter(Appointment.doctor_id == doctor_id)
    if status:
        q = q.filter(Appointment.status == status)
    appts = q.order_by(Appointment.queue_number, Appointment.start_time).all()
    return [_format_appointment(a, db) for a in appts]


@router.get("/schedule")
def get_schedule_summary(
    target_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Return per-doctor summary for a given date."""
    if target_date is None:
        target_date = date.today().isoformat()

    d = date.fromisoformat(target_date)
    dow = d.weekday()

    sessions = db.query(ClinicSession).filter(
        ClinicSession.day_of_week == dow,
        ClinicSession.is_active == True,
    ).all()

    result = []
    for s in sessions:
        doctor = db.query(Doctor).filter(Doctor.id == s.doctor_id).first()
        appts = (
            db.query(Appointment)
            .filter(
                Appointment.session_id == s.id,
                Appointment.date == target_date,
                Appointment.status == "CONFIRMED",
            )
            .order_by(Appointment.queue_number, Appointment.start_time)
            .all()
        )
        result.append({
            "session_id": s.id,
            "doctor_id": s.doctor_id,
            "doctor_name": doctor.name if doctor else "",
            "doctor_title": doctor.title if doctor else "",
            "session_type": s.session_type,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "booked": len(appts),
            "capacity": s.max_queue if s.session_type == "NHI" else None,
            "appointments": [_format_appointment(a, db) for a in appts],
        })
    return {"date": target_date, "sessions": result}


@router.get("/doctors")
def list_all_doctors(db: Session = Depends(get_db)):
    doctors = db.query(Doctor).filter(Doctor.is_active == True).all()
    return [{"id": d.id, "name": d.name, "title": d.title} for d in doctors]


@router.put("/appointments/{appt_id}/status")
def update_status(
    appt_id: str,
    status: str = Query(...),   # CONFIRMED | CANCELLED | COMPLETED | NO_SHOW
    db: Session = Depends(get_db),
):
    valid = {"CONFIRMED", "CANCELLED", "COMPLETED", "NO_SHOW"}
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of {valid}")

    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(404, "預約不存在")

    appt.status = status
    db.commit()
    return {"message": "狀態已更新", "status": status}
