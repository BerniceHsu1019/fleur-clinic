import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import Doctor, ClinicSession, Patient, Appointment
from lib.slot_generator import get_block_status, time_to_minutes
from lib.his_adapter import his

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


class BookingRequest(BaseModel):
    appointment_type: str     # PRIVATE_GROWTH | PRIVATE_MENTAL
    session_id: str
    date: str                 # "2026-01-15"
    visit_type: str           # FIRST | RETURN
    block_start: str          # :00/:30 boundary, e.g. "09:00"
    # Patient details
    name: str                 # guardian / adult name
    phone: str
    child_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    notes: Optional[str] = None
    nhi_number: Optional[str] = None  # kept for possible NHI future use


@router.post("")
def create_appointment(req: BookingRequest, db: Session = Depends(get_db)):
    valid_types = {"PRIVATE_GROWTH", "PRIVATE_MENTAL"}
    if req.appointment_type not in valid_types:
        raise HTTPException(400, "無效的掛號類型")

    session = db.query(ClinicSession).filter(ClinicSession.id == req.session_id).first()
    if not session:
        raise HTTPException(404, "診次不存在")

    if session.session_type != "PRIVATE":
        raise HTTPException(400, "健保門診請至診所現場取號")

    # Existing confirmed appointments for this session/date
    existing = (
        db.query(Appointment)
        .filter(
            Appointment.session_id == req.session_id,
            Appointment.date == req.date,
            Appointment.status == "CONFIRMED",
        )
        .all()
    )

    # Validate block_start is a :00/:30 position
    block_min = time_to_minutes(req.block_start)
    if block_min % 30 != 0:
        raise HTTPException(400, "時段必須為整點或半點（:00 或 :30）")

    block = get_block_status(block_min, existing)

    if req.visit_type == "FIRST":
        if not block["available_for_first"]:
            raise HTTPException(409, "此時段無法預約初診，請選擇其他時段")
        slot = block["next_slot_first"]
    elif req.visit_type == "RETURN":
        if not block["available_for_return"]:
            raise HTTPException(409, "此時段無法預約複診，請選擇其他時段")
        slot = block.get("next_slot_return") or block.get("next_slot_first")
    else:
        raise HTTPException(400, "visit_type 必須為 FIRST 或 RETURN")

    start_time = slot["start"]
    end_time = slot["end"]

    # Upsert patient by phone
    patient = db.query(Patient).filter(Patient.phone == req.phone).first()
    if not patient:
        patient = Patient(
            id=str(uuid.uuid4()),
            name=req.name,
            phone=req.phone,
            nhi_number=req.nhi_number,
            child_name=req.child_name,
            date_of_birth=req.date_of_birth,
        )
        db.add(patient)
    else:
        patient.name = req.name
        if req.child_name:
            patient.child_name = req.child_name
        if req.nhi_number:
            patient.nhi_number = req.nhi_number

    appt = Appointment(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        doctor_id=session.doctor_id,
        session_id=req.session_id,
        date=req.date,
        start_time=start_time,
        end_time=end_time,
        appointment_type=req.appointment_type,
        visit_type=req.visit_type,
        status="CONFIRMED",
        notes=req.notes,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    db.refresh(patient)

    doctor = db.query(Doctor).filter(Doctor.id == session.doctor_id).first()
    his_id = his.sync_appointment(appt, patient, doctor)
    if his_id:
        appt.his_synced = True
        appt.his_id = his_id
        db.commit()

    return {
        "id": appt.id,
        "start_time": appt.start_time,
        "end_time": appt.end_time,
        "date": appt.date,
        "appointment_type": appt.appointment_type,
        "visit_type": appt.visit_type,
        "doctor_name": doctor.name,
        "doctor_title": doctor.title,
        "patient_name": patient.child_name or patient.name,
        "status": appt.status,
        "his_id": appt.his_id,
    }


@router.get("/lookup")
def lookup_appointment(phone: str = Query(...), db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.phone == phone).first()
    if not patient:
        return []

    appts = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient.id,
            Appointment.status == "CONFIRMED",
        )
        .order_by(Appointment.date, Appointment.start_time)
        .all()
    )

    result = []
    for a in appts:
        doctor = db.query(Doctor).filter(Doctor.id == a.doctor_id).first()
        result.append({
            "id": a.id,
            "date": a.date,
            "doctor_name": doctor.name if doctor else "",
            "appointment_type": a.appointment_type,
            "visit_type": a.visit_type,
            "start_time": a.start_time,
            "end_time": a.end_time,
            "status": a.status,
        })
    return result


@router.delete("/{appt_id}")
def cancel_appointment(appt_id: str, db: Session = Depends(get_db)):
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(404, "預約不存在")
    if appt.status != "CONFIRMED":
        raise HTTPException(400, "此預約已取消或完成")
    appt.status = "CANCELLED"
    if appt.his_id:
        his.cancel_appointment(appt.his_id)
    db.commit()
    return {"message": "預約已取消"}
