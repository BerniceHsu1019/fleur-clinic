"""
Seed initial doctors and clinic schedule.
Run: python seed.py
"""
import uuid
from database import SessionLocal, engine, Base
from models import Doctor, ClinicSession

Base.metadata.create_all(bind=engine)

# Active doctors in the booking system
DOCTORS = [
    {
        "name": "黃彥鈞", "title": "醫師",
        "specialty": "小兒內分泌科",
        "supports_nhi": True, "supports_growth": True, "supports_mental": False,
    },
    {
        "name": "鐘明澤", "title": "醫師",
        "specialty": "小兒內分泌科",
        "supports_nhi": True, "supports_growth": True, "supports_mental": False,
    },
    {
        "name": "鄧智若", "title": "醫師",
        "specialty": "兒童精神科",
        "supports_nhi": True, "supports_growth": False, "supports_mental": True,
    },
    {
        "name": "張恩碩", "title": "醫師",
        "specialty": "小兒腸胃科",
        "supports_nhi": True, "supports_growth": False, "supports_mental": False,
    },
]

# Clinic operating schedule (day_of_week: 0=Mon … 6=Sun)
# Mon-Wed (0-2), Sat (5): morning + afternoon + evening
# Thu (3):                afternoon + evening
# Fri (4), Sun (6):       closed
MORNING_DAYS   = [0, 1, 2, 5]   # Mon-Wed, Sat
AFTERNOON_DAYS = [0, 1, 2, 3, 5] # Mon-Thu, Sat
EVENING_DAYS   = [0, 1, 2, 3, 5] # Mon-Thu, Sat

SESSIONS = [
    (MORNING_DAYS,   "08:30", "12:00"),
    (AFTERNOON_DAYS, "14:00", "17:30"),
    (EVENING_DAYS,   "18:00", "21:00"),
]

# NHI capacity per session (9 patients per 30-min block when no private)
NHI_CAPACITY = {
    ("08:30", "12:00"): 63,   # 7 blocks × 9
    ("14:00", "17:30"): 63,   # 7 blocks × 9
    ("18:00", "21:00"): 54,   # 6 blocks × 9
}


def build_sessions(doctor_id: str, supports_nhi: bool, supports_private: bool) -> list:
    sessions = []
    for days, start, end in SESSIONS:
        for day in days:
            if supports_nhi:
                sessions.append(ClinicSession(
                    id=str(uuid.uuid4()),
                    doctor_id=doctor_id,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                    session_type="NHI",
                    max_queue=NHI_CAPACITY[(start, end)],
                    is_active=True,
                ))
            if supports_private:
                sessions.append(ClinicSession(
                    id=str(uuid.uuid4()),
                    doctor_id=doctor_id,
                    day_of_week=day,
                    start_time=start,
                    end_time=end,
                    session_type="PRIVATE",
                    is_active=True,
                ))
    return sessions


def main():
    db = SessionLocal()
    try:
        if db.query(Doctor).count() > 0:
            print("Database already seeded. Skipping.")
            return

        for d_data in DOCTORS:
            doctor = Doctor(
                id=str(uuid.uuid4()),
                name=d_data["name"],
                title=d_data["title"],
                specialty=d_data["specialty"],
                supports_nhi=d_data["supports_nhi"],
                supports_growth=d_data["supports_growth"],
                supports_mental=d_data["supports_mental"],
                is_active=True,
            )
            db.add(doctor)
            db.flush()

            supports_private = d_data["supports_growth"] or d_data["supports_mental"]
            for s in build_sessions(doctor.id, d_data["supports_nhi"], supports_private):
                db.add(s)

        db.commit()
        doctor_count = db.query(Doctor).count()
        session_count = db.query(ClinicSession).count()
        print(f"Seeded {doctor_count} doctors, {session_count} clinic sessions.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
