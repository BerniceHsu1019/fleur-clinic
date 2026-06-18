"""
NHI walk-in online queue.
Queue numbers are SHARED across all doctors in the same session period (早/午/晚診).
New numbers stop being issued 10 minutes before the session ends.
"""
import uuid
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Doctor, ClinicSession, Patient, Appointment
from lib.his_adapter import his

router = APIRouter(prefix="/api/nhi-queue", tags=["nhi-queue"])


def session_period_label(start_time: str) -> str:
    h = int(start_time.split(":")[0])
    if h < 12:
        return "早診"
    if h < 17:
        return "午診"
    return "晚診"


def time_to_minutes(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def minutes_to_time(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}"


@router.get("/sessions")
def get_today_sessions(db: Session = Depends(get_db)):
    """Today's NHI periods (early/afternoon/evening) with shared queue counts."""
    today = date.today()
    now = datetime.now().strftime("%H:%M")
    dow = today.weekday()

    sessions = (
        db.query(ClinicSession)
        .filter(
            ClinicSession.day_of_week == dow,
            ClinicSession.session_type == "NHI",
            ClinicSession.is_active == True,
        )
        .order_by(ClinicSession.start_time)
        .all()
    )

    # Group by start_time so all doctors in the same period share one entry
    period_map: dict = {}
    for s in sessions:
        period_map.setdefault(s.start_time, []).append(s)

    result = []
    for start_time in sorted(period_map.keys()):
        period_sessions = period_map[start_time]
        end_time = period_sessions[0].end_time
        all_ids = [s.id for s in period_sessions]

        queue_count = (
            db.query(Appointment)
            .filter(
                Appointment.session_id.in_(all_ids),
                Appointment.date == today.isoformat(),
                Appointment.status == "CONFIRMED",
            )
            .count()
        )

        total_max = sum(s.max_queue for s in period_sessions)
        cutoff = minutes_to_time(time_to_minutes(end_time) - 10)

        is_ended = now >= end_time
        is_past_cutoff = (not is_ended) and (now >= cutoff)
        is_full = queue_count >= total_max
        is_open = not is_ended and not is_past_cutoff and not is_full

        result.append({
            "period_start": start_time,
            "period_end": end_time,
            "cutoff_time": cutoff,
            "label": session_period_label(start_time),
            "current_queue": queue_count,
            "max_queue": total_max,
            "is_open": is_open,
            "is_ended": is_ended,
            "is_past_cutoff": is_past_cutoff,
            "is_full": is_full,
        })

    return {"date": today.isoformat(), "now": now, "sessions": result}


class QueueRequest(BaseModel):
    period_start: str          # "08:30" — identifies which session period
    name: str
    phone: str
    nhi_number: Optional[str] = None
    patient_name: Optional[str] = None
    date_of_birth: Optional[str] = None


@router.post("/register")
def register_queue(req: QueueRequest, db: Session = Depends(get_db)):
    today = date.today()
    now = datetime.now().strftime("%H:%M")
    dow = today.weekday()

    period_sessions = (
        db.query(ClinicSession)
        .filter(
            ClinicSession.day_of_week == dow,
            ClinicSession.session_type == "NHI",
            ClinicSession.start_time == req.period_start,
            ClinicSession.is_active == True,
        )
        .all()
    )

    if not period_sessions:
        raise HTTPException(404, "診次不存在")

    end_time = period_sessions[0].end_time
    cutoff = minutes_to_time(time_to_minutes(end_time) - 10)

    if now >= end_time:
        raise HTTPException(400, f"此診次已於 {end_time} 結束，無法取號")

    if now >= cutoff:
        raise HTTPException(400, f"門診將於 {end_time} 結束，{cutoff} 後停止取號")

    all_ids = [s.id for s in period_sessions]

    confirmed_appts = (
        db.query(Appointment)
        .filter(
            Appointment.session_id.in_(all_ids),
            Appointment.date == today.isoformat(),
            Appointment.status == "CONFIRMED",
        )
        .all()
    )

    total_max = sum(s.max_queue for s in period_sessions)
    if len(confirmed_appts) >= total_max:
        raise HTTPException(409, "此診次號碼已滿，請現場候補")

    # Duplicate: same phone already registered for this period today
    existing = (
        db.query(Appointment)
        .join(Patient, Patient.id == Appointment.patient_id)
        .filter(
            Patient.phone == req.phone,
            Appointment.session_id.in_(all_ids),
            Appointment.date == today.isoformat(),
            Appointment.status == "CONFIRMED",
        )
        .first()
    )
    label = session_period_label(req.period_start)
    if existing:
        return {
            "queue_number": existing.queue_number,
            "label": label,
            "start_time": req.period_start,
            "end_time": end_time,
            "date": today.isoformat(),
            "already_registered": True,
        }

    # Store under the first session as representative
    rep_session = period_sessions[0]

    patient = db.query(Patient).filter(Patient.phone == req.phone).first()
    if not patient:
        patient = Patient(
            id=str(uuid.uuid4()),
            name=req.name,
            phone=req.phone,
            nhi_number=req.nhi_number,
            child_name=req.patient_name,
            date_of_birth=req.date_of_birth,
        )
        db.add(patient)
    else:
        patient.name = req.name
        if req.nhi_number:
            patient.nhi_number = req.nhi_number
        if req.patient_name:
            patient.child_name = req.patient_name

    queue_number = len(confirmed_appts) + 1
    appt = Appointment(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        doctor_id=rep_session.doctor_id,
        session_id=rep_session.id,
        date=today.isoformat(),
        queue_number=queue_number,
        appointment_type="NHI",
        status="CONFIRMED",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    db.refresh(patient)

    doctor = db.query(Doctor).filter(Doctor.id == rep_session.doctor_id).first()
    his_id = his.sync_appointment(appt, patient, doctor)
    if his_id:
        appt.his_synced = True
        appt.his_id = his_id
        db.commit()

    return {
        "queue_number": queue_number,
        "label": label,
        "start_time": req.period_start,
        "end_time": end_time,
        "date": today.isoformat(),
        "his_id": appt.his_id,
        "already_registered": False,
    }
