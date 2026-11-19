import json
import os
import re
import uuid
from datetime import date, datetime

from modules.meetings.meeting_tool import MeetingTool
from modules.module6_llm import LlmClient


class AppointmentDetector(MeetingTool):
    """Repère, dans la transcription d'une réunion, les rendez-vous donnés à voix haute."""

    def __init__(self, meetings_service):
        super().__init__(meetings_service=meetings_service)
        self.context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_meeting_appointments.txt")
        )
        self.hint_words = (
            self.meetings_service.week_days
            + self.meetings_service.months
            + ["demain", "prochain", "semaine", "heure"]
        )
        self.max_appointments = 20


    def has_hint(self, text):

        lower_text = text.lower()

        return any(char.isdigit() for char in lower_text) or any(word in lower_text for word in self.hint_words)


    def parse(self, answer):

        start = answer.find("[")
        end = answer.rfind("]")

        if start == -1 or end == -1:
            return []

        try:
            raw_appointments = json.loads(answer[start:end + 1])
        except ValueError:
            return []

        appointments = []

        for raw in raw_appointments:
            if not isinstance(raw, dict):
                continue

            try:
                appointment_date = datetime.strptime(str(raw.get("date")), "%Y-%m-%d").date()
            except ValueError:
                continue

            if appointment_date < date.today():
                continue

            appointment_time = raw.get("time")

            if not isinstance(appointment_time, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", appointment_time):
                appointment_time = None

            person = raw.get("with")
            person = " ".join(person.split())[:60] if isinstance(person, str) and person.strip() else None

            appointments.append({
                "title": str(raw.get("title") or "Rendez-vous")[:120],
                "date": appointment_date.isoformat(),
                "time": appointment_time,
                "with": person,
                "source_sentence": str(raw.get("source_sentence") or "")[:300],
            })

        return appointments


    def make_key(self, appointment):
        return (appointment["date"], appointment["time"], appointment["title"].lower())


    def detect_in_chunk(self, chunk_text):

        answer = self.meetings_service.llm_client.ask_paced(
            context=self.context,
            text_interaction=self.meetings_service.get_calendar_text() + "\n\nExtrait de la réunion :\n" + chunk_text,
        )

        return self.parse(answer=answer)


    def detect(self, meeting_id):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        if not meeting["chunks"]:
            raise ValueError("Cette réunion n'a pas encore de transcription.")

        known = meeting.setdefault("appointments", [])
        known_keys = {self.make_key(appointment) for appointment in known}
        failed_chunks = 0

        for chunk_text in meeting["chunks"]:

            if not self.has_hint(text=chunk_text):
                continue

            try:
                found = self.detect_in_chunk(chunk_text=chunk_text)
            except Exception:
                failed_chunks += 1
                continue

            for appointment in found:
                if self.make_key(appointment) in known_keys or len(known) >= self.max_appointments:
                    continue

                appointment["appointment_id"] = uuid.uuid4().hex[:8]
                appointment["status"] = "proposed"
                known.append(appointment)
                known_keys.add(self.make_key(appointment))

        self.save_meeting(meeting_id=meeting_id)

        return {"appointments": known, "failed_chunks": failed_chunks}