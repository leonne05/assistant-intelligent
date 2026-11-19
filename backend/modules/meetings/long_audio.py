import time


class MeetingAudioProcessor:
    def __init__(self, meetings_service, splitter):
        self.meetings_service = meetings_service
        self.splitter = splitter
        self.jobs = {}

        self.max_audio_bytes = 600 * 1024 * 1024
        self.tokens_needed = 5000
        self.max_attempts = 3
        self.retry_wait = 30


    def prepare(self, meeting_id, audio_file_name, audio_bytes, user_consent):

        meeting = self.meetings_service.meetings.get(meeting_id)

        if meeting is None:
            return None

        if not user_consent:
            raise PermissionError("Autorisation refusée : je n'enregistre pas sans ton accord.")

        self.meetings_service.check_participants_consent(meeting=meeting)

        if len(audio_bytes) == 0:
            raise ValueError("Le fichier audio est vide.")

        if len(audio_bytes) > self.max_audio_bytes:
            raise ValueError("Le fichier audio dépasse 600 Mo.")

        job = self.jobs.get(meeting_id)

        if job is not None and job["status"] in ("splitting", "transcribing"):
            raise ValueError("Un audio est déjà en cours de traitement pour cette réunion.")

        self.jobs[meeting_id] = {
            "file_name": audio_file_name,
            "status": "splitting",
            "part_count": 0,
            "done_parts": 0,
            "error": None,
        }

        return self.jobs[meeting_id]


    def process(self, meeting_id, audio_file_name, audio_bytes):

        job = self.jobs[meeting_id]

        try:
            parts = self.splitter.split(audio_file_name=audio_file_name, audio_bytes=audio_bytes)

            job["part_count"] = len(parts)
            job["status"] = "transcribing"

            for index, (part_name, part_bytes) in enumerate(parts):
                self.transcribe_part(meeting_id=meeting_id, part_name=part_name, part_bytes=part_bytes)
                job["done_parts"] = index + 1

            job["status"] = "done"

        except Exception as error:
            job["status"] = "error"
            job["error"] = str(error)


    def transcribe_part(self, meeting_id, part_name, part_bytes):

        for attempt in range(self.max_attempts):
            try:
                self.meetings_service.llm_client.wait_for_budget(tokens=self.tokens_needed)

                return self.meetings_service.transcribe_chunk(
                    meeting_id=meeting_id,
                    audio_file_name=part_name,
                    audio_bytes=part_bytes,
                    user_consent=True,
                )
            except (PermissionError, ValueError):
                raise
            except Exception:
                if attempt == self.max_attempts - 1:
                    raise

                time.sleep(self.retry_wait)


    def get_status(self, meeting_id):

        job = self.jobs.get(meeting_id)

        if job is None:
            return None

        meeting = self.meetings_service.meetings.get(meeting_id)

        return {**job, "chunk_count": meeting["chunk_count"] if meeting else 0}