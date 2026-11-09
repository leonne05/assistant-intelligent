import time


class LongAudioProcessor:
    def __init__(self, study_service, splitter):
        self.study_service = study_service
        self.splitter = splitter
        self.jobs = {}

        self.max_audio_bytes = 600 * 1024 * 1024
        self.tokens_needed = 5000
        self.max_attempts = 3
        self.retry_wait = 30


    def prepare(self, course_id, audio_file_name, audio_bytes, user_consent):

        if not user_consent:
            raise PermissionError("Autorisation refusée : je ne transcris pas sans ton accord.")

        if len(audio_bytes) == 0:
            raise ValueError("Le fichier audio est vide.")

        if len(audio_bytes) > self.max_audio_bytes:
            raise ValueError("Le fichier audio dépasse 600 Mo.")

        job = self.jobs.get(course_id)

        if job is not None and job["status"] in ("splitting", "transcribing"):
            raise ValueError("Un audio est déjà en cours de traitement pour ce cours.")

        self.jobs[course_id] = {
            "file_name": audio_file_name,
            "status": "splitting",
            "part_count": 0,
            "done_parts": 0,
            "error": None,
        }


    def process(self, course_id, audio_file_name, audio_bytes):

        job = self.jobs[course_id]

        try:
            parts = self.splitter.split(audio_file_name=audio_file_name, audio_bytes=audio_bytes)

            job["part_count"] = len(parts)
            job["status"] = "transcribing"

            for index, (part_name, part_bytes) in enumerate(parts):
                self.transcribe_part(course_id=course_id, part_name=part_name, part_bytes=part_bytes)
                job["done_parts"] = index + 1

            job["status"] = "done"

        except Exception as error:
            job["status"] = "error"
            job["error"] = str(error)


    def transcribe_part(self, course_id, part_name, part_bytes):

        for attempt in range(self.max_attempts):
            try:
                self.study_service.llm_client.wait_for_budget(tokens=self.tokens_needed)

                course = self.study_service.courses.get(course_id)
                chunk_index = course["chunk_count"] + 1 if course else 1

                return self.study_service.transcribe_chunk(
                    course_id=course_id,
                    chunk_index=chunk_index,
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


    def get_status(self, course_id):

        job = self.jobs.get(course_id)

        if job is None:
            return None

        course = self.study_service.courses.get(course_id)

        return {**job, "chunk_count": course["chunk_count"] if course else 0}