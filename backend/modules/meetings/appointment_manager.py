import re
from datetime import datetime, timedelta

from modules.meetings.meeting_tool import MeetingTool


class AppointmentManager(MeetingTool):
    """Gère les rendez-vous détectés : l'utilisateur les accepte (ajout à l'agenda) ou les refuse."""

    def __init__(self, meetings_service, agenda_source, conflict_detector):
        super().__init__(meetings_service=meetings_service)
        self.agenda_source = agenda_source
        self.conflict_detector = conflict_detector

        self.default_duration = 60
        self.min_duration = 5
        self.max_duration = 480


    def list_appointments(self, meeting_id):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        return meeting.get("appointments", [])


    def find_appointment(self, meeting, appointment_id):

        for appointment in meeting.get("appointments", []):
            if appointment["appointment_id"] == appointment_id:
                return appointment

        return None


    def get_start_and_end(self, appointment, time, duration_minutes):

        time = time or appointment["time"]

        if not time:
            raise ValueError("Il manque l'heure de ce rendez-vous : donne-la au format HH:MM, par exemple 14:00.")

        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", time):
            raise ValueError("L'heure doit être au format HH:MM, par exemple 14:00.")

        if not self.min_duration <= duration_minutes <= self.max_duration:
            raise ValueError(f"La durée doit être entre {self.min_duration} et {self.max_duration} minutes.")

        start = datetime.fromisoformat(f"{appointment['date']}T{time}")

        return start, start + timedelta(minutes=duration_minutes)


    def accept(self, meeting_id, appointment_id, time=None, duration_minutes=None, ignore_conflicts=False):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        appointment = self.find_appointment(meeting=meeting, appointment_id=appointment_id)

        if appointment is None:
            return False

        if appointment["status"] == "in_agenda":
            raise ValueError("Ce rendez-vous est déjà dans l'agenda.")

        duration_minutes = duration_minutes or self.default_duration
        start, end = self.get_start_and_end(appointment=appointment, time=time, duration_minutes=duration_minutes)

        conflicts = self.conflict_detector.find_conflicts(start=start, end=end)

        if conflicts and not ignore_conflicts:
            free_slot = self.conflict_detector.find_free_slot(
                day=start.date(), duration_minutes=duration_minutes, earliest=start
            )
            return {"added": False, "appointment": appointment, "conflicts": conflicts, "free_slot": free_slot}

        title = appointment["title"]

        if appointment["with"] and appointment["with"].lower() not in title.lower():
            title = f"{title} (avec {appointment['with']})"

        event = self.agenda_source.add_event(
            title=title, start=start.isoformat(timespec="minutes"), end=end.isoformat(timespec="minutes")
        )

        appointment["status"] = "in_agenda"
        appointment["time"] = start.strftime("%H:%M")
        appointment["duration_minutes"] = duration_minutes
        appointment["agenda_event_id"] = event["event_id"]
        self.save_meeting(meeting_id=meeting_id)

        return {"added": True, "appointment": appointment, "conflicts": conflicts, "free_slot": None}


    def reject(self, meeting_id, appointment_id):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        appointment = self.find_appointment(meeting=meeting, appointment_id=appointment_id)

        if appointment is None:
            return False

        if appointment["status"] == "in_agenda":
            raise ValueError("Ce rendez-vous est déjà dans l'agenda : supprime-le d'abord de l'agenda.")

        appointment["status"] = "rejected"
        self.save_meeting(meeting_id=meeting_id)

        return appointment