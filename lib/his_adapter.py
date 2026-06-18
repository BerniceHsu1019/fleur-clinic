"""
MediSign HIS Adapter (mock implementation).

Replace the methods below with real HTTP calls to the MediSign API
once API credentials and documentation are available.

MediSign product: https://smart-healthcare.com.tw/medisign/
Contact: obtain API key and base URL from MediSign sales team.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Placeholder — set via environment variable in production
HIS_BASE_URL = "https://his.medisign.example.com/api"
HIS_API_KEY = "REPLACE_WITH_REAL_KEY"


class HISAdapter:
    def sync_appointment(self, appointment, patient, doctor) -> Optional[str]:
        """
        Push a confirmed appointment to MediSign.
        Returns the HIS appointment ID on success, None on failure.
        """
        payload = {
            "patientName": patient.child_name or patient.name,
            "patientPhone": patient.phone,
            "nhiNumber": patient.nhi_number,
            "doctorName": doctor.name,
            "appointmentDate": appointment.date,
            "startTime": appointment.start_time,
            "endTime": appointment.end_time,
            "queueNumber": appointment.queue_number,
            "appointmentType": appointment.appointment_type,
            "visitType": appointment.visit_type,
        }
        # --- MOCK: log and return a fake HIS ID ---
        logger.info("[HIS MOCK] Would POST to %s/appointments: %s", HIS_BASE_URL, payload)
        mock_his_id = f"HIS-{appointment.id[:8].upper()}"
        logger.info("[HIS MOCK] Returning mock HIS ID: %s", mock_his_id)
        return mock_his_id

    def cancel_appointment(self, his_id: str) -> bool:
        """Cancel an appointment in MediSign by HIS appointment ID."""
        logger.info("[HIS MOCK] Would DELETE %s/appointments/%s", HIS_BASE_URL, his_id)
        return True

    def get_patient(self, nhi_number: str) -> Optional[dict]:
        """Look up patient in HIS by NHI number."""
        logger.info("[HIS MOCK] Would GET %s/patients?nhi=%s", HIS_BASE_URL, nhi_number)
        return None  # not found in mock


his = HISAdapter()
