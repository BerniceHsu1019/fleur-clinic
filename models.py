import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime, Date, Enum, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from database import Base
import enum


def gen_id():
    return str(uuid.uuid4())


class SessionType(str, enum.Enum):
    NHI = "NHI"
    PRIVATE = "PRIVATE"


class AppointmentType(str, enum.Enum):
    NHI = "NHI"
    PRIVATE_GROWTH = "PRIVATE_GROWTH"   # 生長發育
    PRIVATE_MENTAL = "PRIVATE_MENTAL"   # 兒童心智發展


class VisitType(str, enum.Enum):
    FIRST = "FIRST"
    RETURN = "RETURN"


class AppointmentStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    title = Column(String, nullable=False)          # 醫師 / 營養師 / 體能教練
    specialty = Column(String, nullable=False)
    supports_nhi = Column(Boolean, default=False)
    supports_growth = Column(Boolean, default=False)   # 生長發育門診
    supports_mental = Column(Boolean, default=False)   # 兒童心智發展門診
    is_active = Column(Boolean, default=True)

    sessions = relationship("ClinicSession", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")


class ClinicSession(Base):
    """Weekly recurring schedule template for a doctor."""
    __tablename__ = "clinic_sessions"

    id = Column(String, primary_key=True, default=gen_id)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)   # 0=Mon … 6=Sun
    start_time = Column(String, nullable=False)     # "08:30"
    end_time = Column(String, nullable=False)       # "12:00"
    session_type = Column(String, nullable=False)   # NHI | PRIVATE
    max_queue = Column(Integer, default=60)         # NHI sessions only
    is_active = Column(Boolean, default=True)

    doctor = relationship("Doctor", back_populates="sessions")
    appointments = relationship("Appointment", back_populates="session")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)           # guardian / adult name
    phone = Column(String, nullable=False)
    nhi_number = Column(String, nullable=True)
    child_name = Column(String, nullable=True)      # patient (child) name
    date_of_birth = Column(String, nullable=True)   # ISO date string
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointments = relationship("Appointment", back_populates="patient")


class ScheduleException(Base):
    """Marks a doctor as unavailable on a specific date (all sessions or one session)."""
    __tablename__ = "schedule_exceptions"

    id = Column(String, primary_key=True, default=gen_id)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    date = Column(String, nullable=False)              # "2026-07-22"
    session_start_time = Column(String, nullable=True) # None = whole day; "14:00" = that session only
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    doctor = relationship("Doctor")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(String, ForeignKey("doctors.id"), nullable=False)
    session_id = Column(String, ForeignKey("clinic_sessions.id"), nullable=False)
    date = Column(String, nullable=False)           # ISO date "2025-01-15"
    start_time = Column(String, nullable=True)      # private: "14:00"
    end_time = Column(String, nullable=True)        # private: "14:20"
    queue_number = Column(Integer, nullable=True)   # NHI queue
    appointment_type = Column(String, nullable=False)
    visit_type = Column(String, nullable=True)      # FIRST | RETURN
    status = Column(String, default="CONFIRMED")
    notes = Column(Text, nullable=True)
    his_synced = Column(Boolean, default=False)
    his_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    session = relationship("ClinicSession", back_populates="appointments")
