"""
Seed doctors and clinic schedule.
Each doctor has their own specific days/sessions based on the actual schedule.
Re-seeds automatically when doctor list changes.
"""
import uuid
from database import SessionLocal, engine, Base
from models import Doctor, ClinicSession, Patient, Appointment, ScheduleException

Base.metadata.create_all(bind=engine)

DOCTORS = [
    {
        "name": "黃彥鈞", "title": "醫師",
        "specialty": "小兒內分泌科",
        "supports_nhi": True, "supports_growth": True, "supports_mental": False,
        # (day_of_week, start_time, end_time)  0=Mon … 6=Sun
        "sessions": [
            (1, "14:00", "17:30"),  # Tue 午
            (2, "14:00", "17:30"),  # Wed 午
            (2, "18:00", "21:00"),  # Wed 晚
            (3, "14:00", "17:30"),  # Thu 午
            (3, "18:00", "21:00"),  # Thu 晚
            (4, "14:00", "17:30"),  # Fri 午
            (5, "14:00", "17:30"),  # Sat 午 (rotating with 鐘明澤)
            (5, "18:00", "21:00"),  # Sat 晚 (rotating with 鐘明澤)
        ],
    },
    {
        "name": "鐘明澤", "title": "醫師",
        "specialty": "小兒內分泌科",
        "supports_nhi": True, "supports_growth": True, "supports_mental": False,
        "sessions": [
            (0, "14:00", "17:30"),  # Mon 午
            (0, "18:00", "21:00"),  # Mon 晚
            (1, "08:30", "12:00"),  # Tue 早
            (1, "18:00", "21:00"),  # Tue 晚
            (4, "08:30", "12:00"),  # Fri 早
            (4, "18:00", "21:00"),  # Fri 晚
            (5, "08:30", "12:00"),  # Sat 早 (rotating with 張恩碩)
            (5, "14:00", "17:30"),  # Sat 午 (rotating with 黃彥鈞)
            (5, "18:00", "21:00"),  # Sat 晚 (rotating with 黃彥鈞)
        ],
    },
    {
        "name": "鄧芷若", "title": "醫師",
        "specialty": "兒童精神科",
        "supports_nhi": True, "supports_growth": False, "supports_mental": True,
        "sessions": [
            (1, "18:00", "21:00"),  # Tue 晚
            (4, "18:00", "21:00"),  # Fri 晚
        ],
    },
    {
        "name": "張恩碩", "title": "醫師",
        "specialty": "小兒腸胃科",
        "supports_nhi": True, "supports_growth": False, "supports_mental": False,
        "sessions": [
            (0, "08:30", "12:00"),  # Mon 早
            (2, "08:30", "12:00"),  # Wed 早
            (5, "08:30", "12:00"),  # Sat 早 (rotating with 鐘明澤)
        ],
    },
]

NHI_CAPACITY = {
    "08:30": 63,   # 7 blocks × 9
    "14:00": 63,   # 7 blocks × 9
    "18:00": 54,   # 6 blocks × 9
}


def build_sessions(doctor_id: str, supports_nhi: bool, supports_private: bool, schedule: list) -> list:
    sessions = []
    for day, start, end in schedule:
        if supports_nhi:
            sessions.append(ClinicSession(
                id=str(uuid.uuid4()),
                doctor_id=doctor_id,
                day_of_week=day,
                start_time=start,
                end_time=end,
                session_type="NHI",
                max_queue=NHI_CAPACITY.get(start, 54),
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
        existing_names = {d.name for d in db.query(Doctor).all()}
        expected_names = {d["name"] for d in DOCTORS}

        if existing_names == expected_names:
            print("Database already seeded with current doctor list. Skipping.")
            return

        # Clear all existing data and re-seed
        print("Re-seeding database with updated schedule...")
        db.query(Appointment).delete()
        db.query(ScheduleException).delete()
        db.query(ClinicSession).delete()
        db.query(Patient).delete()
        db.query(Doctor).delete()
        db.commit()

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
            for s in build_sessions(doctor.id, d_data["supports_nhi"], supports_private, d_data["sessions"]):
                db.add(s)

        db.commit()
        doctor_count = db.query(Doctor).count()
        session_count = db.query(ClinicSession).count()
        print(f"Seeded {doctor_count} doctors, {session_count} clinic sessions.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
