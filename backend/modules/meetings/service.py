from datetime import datetime
import os
import uuid

from modules.module6_llm import LlmClient
from modules.meetings.meetings_memory import MeetingsMemory


class MeetingsService:
    def __init__(self, database_path=None):
        self.llm_client = LlmClient()
        self.context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_meetings.txt")
        )

        self.max_audio_size = 25 * 1024 * 1024
        self.max_participants = 20
        self.max_agenda_items = 20
        self.default_prompt = "Transcription d'une réunion en français."

        if database_path is None:
            database_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "data", "meetings.db")
            )

        self.memory = MeetingsMemory(database_path=database_path)
        self.meetings = self.memory.load_all_meetings()


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

        previous_text_end = meeting["transcript"][-400:]

        chunk_text = self.llm_client.transcribe(
            audio_file_name=audio_file_name,
            audio_bytes=audio_bytes,
            language="fr",
            prompt=previous_text_end or self.default_prompt,
        )

        meeting["transcript"] = (meeting["transcript"] + " " + chunk_text).strip()
        meeting["chunks"].append(chunk_text)
        meeting["chunk_count"] = chunk_index

        self.save_meeting(meeting_id=meeting_id)

        return {
            "meeting_id": meeting_id,
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "chunk_count": meeting["chunk_count"],
        }