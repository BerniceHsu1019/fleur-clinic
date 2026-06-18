"""
30-minute block slot system for PRIVATE appointments.

Each session is divided into 30-min blocks starting at :00 and :30.
Each block can hold EITHER:
  - 1 first visit (20 min)  →  10 min remains for NHI walk-in
  - 2 return visits (10+10 min) →  10 min remains for NHI walk-in
  - 1 return visit (10 min) →  20 min remains for NHI walk-in
  - nothing              →  30 min remains for NHI walk-in

NHI capacity per block (@ 3 min per patient):
  first visit taken  → 3 NHI patients
  2 return visits    → 3 NHI patients
  1 return visit     → 6 NHI patients
  no private         → 9 NHI patients
"""
from datetime import date, timedelta
from typing import List, Dict, Optional

BLOCK_DURATION = 30   # minutes
FIRST_DURATION = 20   # minutes for initial visit
RETURN_DURATION = 10  # minutes for follow-up
NHI_SLOT_MIN = 3      # minutes per NHI patient


def time_to_minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def minutes_to_time(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def get_block_starts(session_start: str, session_end: str) -> List[int]:
    """All :00/:30 block start positions (in minutes) within a session window."""
    start = time_to_minutes(session_start)
    end = time_to_minutes(session_end)
    blocks = []
    t = start
    while t + BLOCK_DURATION <= end:
        blocks.append(t)
        t += BLOCK_DURATION
    return blocks


def get_block_status(block_start_min: int, appointments: list) -> Dict:
    """
    Compute availability for one 30-min block.

    Returns a dict with:
      block_start, block_end      — human-readable times
      status                      — AVAILABLE | PARTIAL | FULL
      available_for_first         — bool
      available_for_return        — bool
      next_slot_first             — slot dict if first visit can be booked
      next_slot_return            — slot dict if return visit can be booked
      nhi_capacity                — number of NHI patients that fit in remaining time
    """
    block_end = block_start_min + BLOCK_DURATION

    # Collect appointments whose start_time falls within this block
    first_visits, return_visits = [], []
    for a in appointments:
        if not a.start_time:
            continue
        st = time_to_minutes(a.start_time)
        if block_start_min <= st < block_end:
            if a.visit_type == "FIRST":
                first_visits.append(a)
            elif a.visit_type == "RETURN":
                return_visits.append(a)

    # -- Full: first visit already booked --
    if first_visits:
        return {
            "block_start": minutes_to_time(block_start_min),
            "block_end": minutes_to_time(block_end),
            "status": "FULL",
            "available_for_first": False,
            "available_for_return": False,
            "next_slot_first": None,
            "next_slot_return": None,
            "nhi_capacity": (block_end - block_start_min - FIRST_DURATION) // NHI_SLOT_MIN,
        }

    # -- Full: two return visits already booked --
    if len(return_visits) >= 2:
        return {
            "block_start": minutes_to_time(block_start_min),
            "block_end": minutes_to_time(block_end),
            "status": "FULL",
            "available_for_first": False,
            "available_for_return": False,
            "next_slot_first": None,
            "next_slot_return": None,
            "nhi_capacity": (block_end - block_start_min - 2 * RETURN_DURATION) // NHI_SLOT_MIN,
        }

    # -- Partial: one return visit booked, second position is free --
    if len(return_visits) == 1:
        second_start = block_start_min + RETURN_DURATION
        private_used = RETURN_DURATION  # only one return visit so far; patient booking here adds another
        return {
            "block_start": minutes_to_time(block_start_min),
            "block_end": minutes_to_time(block_end),
            "status": "PARTIAL",
            "available_for_first": False,
            "available_for_return": True,
            "next_slot_first": None,
            "next_slot_return": {
                "start": minutes_to_time(second_start),
                "end": minutes_to_time(second_start + RETURN_DURATION),
                "visit_type": "RETURN",
                "position": 2,
            },
            "nhi_capacity": (block_end - block_start_min - 2 * RETURN_DURATION) // NHI_SLOT_MIN,
        }

    # -- Fully available: no private appointments yet --
    return {
        "block_start": minutes_to_time(block_start_min),
        "block_end": minutes_to_time(block_end),
        "status": "AVAILABLE",
        "available_for_first": True,
        "available_for_return": True,
        "next_slot_first": {
            "start": minutes_to_time(block_start_min),
            "end": minutes_to_time(block_start_min + FIRST_DURATION),
            "visit_type": "FIRST",
            "position": 1,
        },
        "next_slot_return": {
            "start": minutes_to_time(block_start_min),
            "end": minutes_to_time(block_start_min + RETURN_DURATION),
            "visit_type": "RETURN",
            "position": 1,
        },
        "nhi_capacity": BLOCK_DURATION // NHI_SLOT_MIN,   # 9 (no private used)
    }


def get_session_blocks(session_start: str, session_end: str, appointments: list) -> List[Dict]:
    """All 30-min blocks in a session with per-block availability."""
    return [
        get_block_status(b, appointments)
        for b in get_block_starts(session_start, session_end)
    ]


def session_has_availability(session_start: str, session_end: str, appointments: list, visit_type: str) -> bool:
    """Quick check: does this session have at least one available block for visit_type?"""
    for b in get_block_starts(session_start, session_end):
        status = get_block_status(b, appointments)
        if visit_type == "FIRST" and status["available_for_first"]:
            return True
        if visit_type == "RETURN" and status["available_for_return"]:
            return True
    return False


def get_available_dates(
    sessions: list,
    existing_appointments: list,
    visit_type: str,
    days_ahead: int = 90,
) -> List[Dict]:
    """
    Return dates in the next `days_ahead` days (default 3 months)
    that have at least one available block for the given visit_type.
    Each date appears at most once even if multiple sessions match.
    """
    today = date.today()
    appts_by_date_session: Dict[tuple, list] = {}
    for a in existing_appointments:
        key = (a.date, a.session_id)
        appts_by_date_session.setdefault(key, []).append(a)

    seen_dates: set = set()
    available = []

    for delta in range(1, days_ahead + 1):
        d = today + timedelta(days=delta)
        dow = d.weekday()
        for session in sessions:
            if session.day_of_week != dow or not session.is_active:
                continue
            taken = appts_by_date_session.get((d.isoformat(), session.id), [])
            if session_has_availability(session.start_time, session.end_time, taken, visit_type):
                if d.isoformat() not in seen_dates:
                    seen_dates.add(d.isoformat())
                    available.append({"date": d.isoformat()})

    return available
