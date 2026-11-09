from datetime import date, datetime, timedelta
import json
import os
import re
import uuid

from modules.module6_llm import LlmClient
from modules.meetings.meetings_memory import MeetingsMemory


class MeetingsService:
    def __init__(self, database_path=None):
        self.llm_client = LlmClient()
        folder = os.path.dirname(__file__)

        self.context = LlmClient.read_file(file_path=os.path.join(folder, "context_meetings.txt"))
        self.chunk_notes_context = LlmClient.read_file(file_path=os.path.join(folder, "context_meeting_chunk.txt"))
        self.report_context = LlmClient.read_file(file_path=os.path.join(folder, "context_meeting_report.txt"))
        self.actions_context = LlmClient.read_file(file_path=os.path.join(folder, "context_meeting_actions.txt"))

        self.week_days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        self.months = [
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        ]

        self.max_audio_size = 25 * 1024 * 1024
        self.max_participants = 20
        self.max_agenda_items = 20
        self.max_notes_size = 20000
        self.max_list_items = 20
        self.default_prompt = "Transcription d'une réunion en français."

        if database_path is None:
            database_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "data", "meetings.db")
            )

        self.memory = MeetingsMemory(database_path=database_path)
        self.meetings = self.memory.load_all_meetings()

        for meeting in self.meetings.values():
            meeting.setdefault("chunk_summaries", [None] * meeting["chunk_count"])
            meeting.setdefault("report", None)


    def get_status(self):
        return {"module": "meetings", "status": "ok"}


    def ask_llm(self, text_interaction):
        return self.llm_client.ask(context=self.context, text_interaction=text_interaction)


    def save_meeting(self, meeting_id):

        if meeting_id in self.meetings:
            self.memory.save_meeting(meeting_id=meeting_id, meeting=self.meetings[meeting_id])


    def update_status(self, meeting):

        consents = [participant["consent"] for participant in meeting["participants"]]

        if False in consents:
            meeting["status"] = "refused"
        elif None in consents:
            meeting["status"] = "waiting_consent"
        else:
            meeting["status"] = "ready"


    def create_meeting(self, title, participants, agenda):

        title = title.strip()

        if not title:
            raise ValueError("La réunion doit avoir un titre.")

        clean_participants = []

        for name in participants:
            name = name.strip()
            already_added = any(known["name"].lower() == name.lower() for known in clean_participants)

            if name and not already_added:
                clean_participants.append({"name": name[:60], "consent": None})

        if len(clean_participants) > self.max_participants:
            raise ValueError(f"Une réunion peut avoir {self.max_participants} participants au maximum.")

        clean_agenda = [item.strip()[:200] for item in agenda if item.strip()]

        if len(clean_agenda) > self.max_agenda_items:
            raise ValueError(f"L'ordre du jour peut avoir {self.max_agenda_items} points au maximum.")

        meeting_id = uuid.uuid4().hex[:8]

        meeting = {
            "meeting_id": meeting_id,
            "title": title[:120],
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "participants": clean_participants,
            "agenda": clean_agenda,
            "status": "waiting_consent",
            "transcript": "",
            "chunk_count": 0,
            "chunks": [],
            "chunk_summaries": [],
            "report": None,
        }

        self.update_status(meeting=meeting)

        self.meetings[meeting_id] = meeting
        self.save_meeting(meeting_id=meeting_id)

        return meeting


    def get_meeting(self, meeting_id):
        return self.meetings.get(meeting_id)


    def list_meetings(self):

        return [
            {
                "meeting_id": meeting_id,
                "title": meeting["title"],
                "created_at": meeting["created_at"],
                "status": meeting["status"],
                "participant_count": len(meeting["participants"]),
                "chunk_count": meeting["chunk_count"],
                "has_report": meeting["report"] is not None,
            }
            for meeting_id, meeting in self.meetings.items()
        ]


    def delete_meeting(self, meeting_id):

        if meeting_id not in self.meetings:
            return False

        del self.meetings[meeting_id]
        self.memory.delete_meeting(meeting_id=meeting_id)

        return True


    def set_consent(self, meeting_id, participant_name, accepted):

        meeting = self.meetings.get(meeting_id)

        if meeting is None:
            return None

        for participant in meeting["participants"]:
            if participant["name"].lower() == participant_name.strip().lower():

                if accepted and meeting["chunk_count"] > 0:
                    raise ValueError("La réunion a déjà commencé : on ne peut plus donner son accord, seulement le retirer.")

                participant["consent"] = accepted
                self.update_status(meeting=meeting)
                self.save_meeting(meeting_id=meeting_id)

                return meeting

        raise ValueError(f"{participant_name} ne fait pas partie des participants de cette réunion.")


    def check_audio(self, audio_bytes, user_consent):

        if not user_consent:
            raise PermissionError("Autorisation refusée : je n'enregistre pas sans ton accord.")

        if len(audio_bytes) == 0:
            raise ValueError("Le fichier audio est vide.")

        if len(audio_bytes) > self.max_audio_size:
            raise ValueError("Le fichier audio dépasse 25 Mo : il faut le découper.")


    def check_participants_consent(self, meeting):

        if meeting["status"] == "refused":
            refused = [participant["name"] for participant in meeting["participants"] if participant["consent"] is False]
            raise PermissionError("Enregistrement impossible : refus de " + ", ".join(refused) + ".")

        if meeting["status"] == "waiting_consent":
            waiting = [participant["name"] for participant in meeting["participants"] if participant["consent"] is None]
            raise PermissionError("Enregistrement impossible : en attente de l'accord de " + ", ".join(waiting) + ".")


    def transcribe_chunk(self, meeting_id, audio_file_name, audio_bytes, user_consent, chunk_index=None):

        meeting = self.meetings.get(meeting_id)

        if meeting is None:
            return None

        self.check_audio(audio_bytes=audio_bytes, user_consent=user_consent)
        self.check_participants_consent(meeting=meeting)

        expected_index = meeting["chunk_count"] + 1

        if chunk_index is None:
            chunk_index = expected_index

        if chunk_index != expected_index:
            raise ValueError(f"Morceau attendu : {expected_index}, reçu : {chunk_index}.")

        chunk_text = self.llm_client.transcribe(
            audio_file_name=audio_file_name,
            audio_bytes=audio_bytes,
            language="fr",
            prompt=self.get_transcription_prompt(meeting=meeting),
        )

        try:
            chunk_summary = self.summarize_chunk(chunk_text=chunk_text)
        except Exception:
            chunk_summary = None

        meeting["transcript"] = (meeting["transcript"] + " " + chunk_text).strip()
        meeting["chunks"].append(chunk_text)
        meeting["chunk_summaries"].append(chunk_summary)
        meeting["chunk_count"] = chunk_index

        self.save_meeting(meeting_id=meeting_id)

        return {
            "meeting_id": meeting_id,
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "chunk_summary": chunk_summary,
            "chunk_count": meeting["chunk_count"],
        }


    def get_transcription_prompt(self, meeting):

        hints = []
        names = [participant["name"] for participant in meeting["participants"]]

        if names:
            hints.append("Participants : " + ", ".join(names) + ".")

        if meeting["agenda"]:
            hints.append("Sujets : " + ", ".join(meeting["agenda"]) + ".")

        hints_text = " ".join(hints)[:200]
        previous_text_end = meeting["transcript"][-250:]

        if previous_text_end:
            return (hints_text + " " + previous_text_end).strip()

        return (self.default_prompt + " " + hints_text).strip()


    def summarize_chunk(self, chunk_text):

        if not chunk_text.strip():
            return None

        return self.llm_client.ask(context=self.chunk_notes_context, text_interaction=chunk_text)


    def format_date(self, day):
        return f"{self.week_days[day.weekday()]} {day.day} {self.months[day.month - 1]} {day.year}"


    def get_calendar_text(self):

        today = date.today()

        lines = [f"Date du jour : {self.format_date(today)} ({today.isoformat()})", "", "Calendrier :"]

        for day_number in range(1, 22):
            day = today + timedelta(days=day_number)
            lines.append(f"- {self.format_date(day)} ({day.isoformat()})")

        return "\n".join(lines)


    def get_meeting_header(self, meeting):

        names = [participant["name"] for participant in meeting["participants"]]
        lines = [
            f"Titre de la réunion : {meeting['title']}",
            f"Date de la réunion : {meeting['created_at'][:10]}",
            "Participants : " + (", ".join(names) if names else "(non précisés)"),
        ]

        if meeting["agenda"]:
            lines.append("Ordre du jour :")
            lines += [f"- {item}" for item in meeting["agenda"]]

        return "\n".join(lines)


    def clean_text_list(self, raw_list):

        if not isinstance(raw_list, list):
            return []

        items = []

        for raw_item in raw_list:
            if isinstance(raw_item, str) and raw_item.strip():
                items.append(raw_item.strip()[:300])

        return items[:self.max_list_items]


    def parse_report_data(self, answer):

        start = answer.find("{")
        end = answer.rfind("}")

        if start == -1 or end == -1:
            return {"decisions": [], "actions": [], "open_points": []}

        try:
            raw_data = json.loads(answer[start:end + 1])
        except ValueError:
            return {"decisions": [], "actions": [], "open_points": []}

        if not isinstance(raw_data, dict):
            return {"decisions": [], "actions": [], "open_points": []}

        actions = []
        raw_actions = raw_data.get("actions")

        if not isinstance(raw_actions, list):
            raw_actions = []

        for raw_action in raw_actions:
            if not isinstance(raw_action, dict):
                continue

            what = raw_action.get("what")

            if not isinstance(what, str) or not what.strip():
                continue

            who = raw_action.get("who")

            if not isinstance(who, str) or not who.strip():
                who = "non précisé"

            due = raw_action.get("due")

            try:
                due = datetime.strptime(str(due), "%Y-%m-%d").date().isoformat()
            except ValueError:
                due = None

            actions.append({
                "id": uuid.uuid4().hex[:8],
                "who": who.strip()[:60],
                "what": what.strip()[:300],
                "due": due,
                "status": "open",
            })

        return {
            "decisions": self.clean_text_list(raw_list=raw_data.get("decisions")),
            "actions": actions[:self.max_list_items],
            "open_points": self.clean_text_list(raw_list=raw_data.get("open_points")),
        }


    def generate_report(self, meeting_id):

        meeting = self.meetings.get(meeting_id)

        if meeting is None:
            return None

        if meeting["chunk_count"] == 0:
            raise ValueError("Cette réunion n'a pas encore de transcription.")

        notes = []

        for index, chunk_text in enumerate(meeting["chunks"]):
            chunk_summary = meeting["chunk_summaries"][index]

            if chunk_summary is None:
                chunk_summary = self.summarize_chunk(chunk_text=chunk_text)
                meeting["chunk_summaries"][index] = chunk_summary

            if chunk_summary is not None:
                notes.append(chunk_summary)

        if not notes:
            raise ValueError("Il n'y a rien à résumer dans cette réunion.")

        all_notes = "\n\n".join(notes)

        if len(all_notes) > self.max_notes_size:
            raise ValueError("Cette réunion est trop longue pour un compte rendu en une fois.")

        meeting_text = self.get_meeting_header(meeting=meeting) + "\n\n## Notes prises pendant la réunion\n\n" + all_notes

        report_text = self.llm_client.ask_paced(
            context=self.report_context,
            text_interaction=meeting_text,
        )

        details_available = True

        try:
            answer = self.llm_client.ask_paced(
                context=self.actions_context,
                text_interaction=self.get_calendar_text() + "\n\n" + meeting_text,
            )
            details = self.parse_report_data(answer=answer)
        except Exception:
            details = {"decisions": [], "actions": [], "open_points": []}
            details_available = False

        meeting["report"] = {
            "text": report_text,
            "decisions": details["decisions"],
            "actions": details["actions"],
            "open_points": details["open_points"],
            "details_available": details_available,
            "status": "draft",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }

        self.save_meeting(meeting_id=meeting_id)

        return meeting["report"]