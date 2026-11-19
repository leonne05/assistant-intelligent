from datetime import date

from modules.meetings.meeting_tool import MeetingTool


class AppointmentNotifier(MeetingTool):
    """Prépare et envoie, avec l'accord de l'utilisateur, un message à la personne du rendez-vous."""

    def __init__(self, meetings_service, sender):
        super().__init__(meetings_service=meetings_service)
        self.sender = sender
        self.max_body_length = 2000


    def find_appointment(self, meeting, appointment_id):

        for appointment in meeting.get("appointments", []):
            if appointment["appointment_id"] == appointment_id:
                return appointment

        return None


    def check_can_message(self, appointment):

        if appointment["status"] == "rejected":
            raise ValueError("Ce rendez-vous a été refusé : je n'écris à personne.")

        if not appointment["with"]:
            raise ValueError("On ne sait pas avec qui est ce rendez-vous : je ne peux pas écrire de message.")


    def build_subject(self, appointment):
        return f"Rendez-vous : {appointment['title']}"


    def build_draft_body(self, appointment):

        day_text = self.meetings_service.format_date(day=date.fromisoformat(appointment["date"]))
        time_text = f" à {appointment['time']}" if appointment["time"] else ""

        return f"Bonjour {appointment['with']},\n\nJe te confirme notre rendez-vous « {appointment['title']} » le {day_text}{time_text}."


    def build_draft(self, meeting_id, appointment_id):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        appointment = self.find_appointment(meeting=meeting, appointment_id=appointment_id)

        if appointment is None:
            return False

        self.check_can_message(appointment=appointment)

        return {
            "recipient": appointment["with"],
            "subject": self.build_subject(appointment=appointment),
            "body": self.build_draft_body(appointment=appointment),
        }


    def send(self, meeting_id, appointment_id, body=None):

        draft = self.build_draft(meeting_id=meeting_id, appointment_id=appointment_id)

        if not draft:
            return draft

        if body is not None:
            body = body.strip()[:self.max_body_length]

            if not body:
                raise ValueError("Le message ne peut pas être vide.")

            draft["body"] = body

        meeting = self.get_meeting(meeting_id=meeting_id)
        appointment = self.find_appointment(meeting=meeting, appointment_id=appointment_id)

        message = self.sender.send(recipient=draft["recipient"], subject=draft["subject"], body=draft["body"])
        meeting.setdefault("outbox", []).append({**message, "appointment_id": appointment_id})
        appointment["message_sent"] = True
        self.save_meeting(meeting_id=meeting_id)

        return {"channel": self.sender.channel, "message": message}