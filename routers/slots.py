from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models import Doctor, ClinicSession, Appointment, ScheduleException
from lib.slot_generator import (
    get_available_dates,
    get_session_blocks,
    time_to_minutes,
)

router = APIRouter(prefix="/api/slots", tags=["slots"])

SESSION_LABELS = {
    "08:30": "早診", "09:00": "早診",
    "14:00": "午診",
    "18:00": "晚診",
}


def session_label(start_time: str) -> str:
    hour = start_time.split(":")[0]
    h = int(hour)
    if h < 12:
        return "早診"
    if h < 17:
        return "午診"
    return "晚診"


@router.get("/dates")
def get_available_dates_for_doctor(
    doctor_id: str = Query(...),
    session_type: str = Query("PRIVATE"),
    visit_type: str = Query(...),   # FIRST | RETURN
    db: Session = Depends(get_db),
):
    """Return list of dates (next 3 months) that have available blocks for visit_type."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(404, "Doctor not found")

    sessions = (
        db.query(ClinicSession)
        .filter(
            ClinicSession.doctor_id == doctor_id,
            ClinicSession.session_type == session_type,
            ClinicSession.is_active == True,
        )
        .all()
    )
    if not sessions:
        return []

    session_ids = [s.id for s in sessions]
    existing = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.session_id.in_(session_ids),
            Appointment.status == "CONFIRMED",
        )
        .all()
    )

    dates = get_available_dates(sessions, existing, visit_type, days_ahead=90)

    # Remove dates blocked by ScheduleException (all-day exceptions for this doctor)
    exceptions = db.query(ScheduleException).filter(
        ScheduleException.doctor_id == doctor_id,
        ScheduleException.session_start_time.is_(None),
    ).all()
    blocked = {e.date for e in exceptions}
    return [d for d in dates if d["date"] not in blocked]


@router.get("/day-blocks")
def get_day_blocks(
    doctor_id: str = Query(...),
    date: str = Query(...),
    visit_type: str = Query(...),   # FIRST | RETURN
    db: Session = Depends(get_db),
):
    """
    Return all 30-min blocks across a doctor's PRIVATE sessions on a given date,
    filtered to only those available for visit_type.
    """
    import datetime
    try:
        d = datetime.date.fromisoformat(date)
    except ValueError:
        raise HTTPException(400, "Invalid date")

    dow = d.weekday()
    sessions = (
        db.query(ClinicSession)
        .filter(
            ClinicSession.doctor_id == doctor_id,
            ClinicSession.session_type == "PRIVATE",
            ClinicSession.day_of_week == dow,
            ClinicSession.is_active == True,
        )
        .order_by(ClinicSession.start_time)
        .all()
    )

    # Check all-day exception
    all_day_exc = db.query(ScheduleException).filter(
        ScheduleException.doctor_id == doctor_id,
        ScheduleException.date == date,
        ScheduleException.session_start_time.is_(None),
    ).first()
    if all_day_exc:
        return []

    result = []
    for session in sessions:
        # Check session-specific exception
        session_exc = db.query(ScheduleException).filter(
            ScheduleException.doctor_id == doctor_id,
            ScheduleException.date == date,
            ScheduleException.session_start_time == session.start_time,
        ).first()
        if session_exc:
            continue

        existing = (
            db.query(Appointment)
            .filter(
                Appointment.session_id == session.id,
                Appointment.date == date,
                Appointment.status == "CONFIRMED",
            )
            .all()
        )
        blocks = get_session_blocks(session.start_time, session.end_time, existing)
        visible_blocks = [
            b for b in blocks
            if (visit_type == "FIRST" and b["available_for_first"])
            or (visit_type == "RETURN" and b["available_for_return"])
        ]
        if visible_blocks:
            result.append({
                "session_id": session.id,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "label": session_label(session.start_time),
                "blocks": visible_blocks,
            })

    return result
