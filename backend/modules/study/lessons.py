class LessonProcessor:
    def __init__(self, study_service, long_audio_processor):
        self.study_service = study_service
        self.long_audio_processor = long_audio_processor
        self.jobs = {}


    def check_audios(self, audios, user_consent):

        if not user_consent:
            raise PermissionError("Autorisation refusée : je ne transcris pas sans ton accord.")

        total_size = 0

        for audio_file_name, audio_bytes in audios:
            if len(audio_bytes) == 0:
                raise ValueError(f"Le fichier audio {audio_file_name} est vide.")

            if len(audio_bytes) > self.long_audio_processor.max_audio_bytes:
                raise ValueError(f"Le fichier audio {audio_file_name} dépasse 600 Mo.")

            total_size += len(audio_bytes)

        if total_size > 4 * self.long_audio_processor.max_audio_bytes:
            raise ValueError("Les fichiers audio sont trop volumineux pour une seule leçon.")


    def prepare(self, course_id, audio_count):

        job = self.jobs.get(course_id)

        if job is not None and job["status"] == "processing":
            raise ValueError("Cette leçon est déjà en cours de traitement.")

        self.jobs[course_id] = {
            "status": "processing",
            "step": "démarrage",
            "audio_count": audio_count,
            "audio_index": 0,
            "error": None,
        }


    def transcribe_audio(self, course_id, audio_file_name, audio_bytes):

        self.long_audio_processor.prepare(
            course_id=course_id,
            audio_file_name=audio_file_name,
            audio_bytes=audio_bytes,
            user_consent=True,
        )
        self.long_audio_processor.process(
            course_id=course_id,
            audio_file_name=audio_file_name,
            audio_bytes=audio_bytes,
        )

        audio_job = self.long_audio_processor.jobs[course_id]

        if audio_job["status"] == "error":
            raise RuntimeError("Audio : " + str(audio_job["error"]))


    def process(self, course_id, audios, pdf_groups):

        job = self.jobs[course_id]
        course = self.study_service.courses[course_id]

        try:
            if not course.get("vocabulary") and pdf_groups:
                job["step"] = "recherche du vocabulaire du cours"
                self.study_service.set_vocabulary(
                    course_id=course_id,
                    terms=self.study_service.extract_vocabulary(text=pdf_groups[0]),
                )

            first_notes_without_vocabulary = 0

            for index, (audio_file_name, audio_bytes) in enumerate(audios):
                job["audio_index"] = index + 1
                job["step"] = f"transcription de l'audio {index + 1} sur {len(audios)}"
                self.transcribe_audio(course_id=course_id, audio_file_name=audio_file_name, audio_bytes=audio_bytes)

                if index == 0 and not course.get("vocabulary"):
                    job["step"] = "recherche du vocabulaire du cours"
                    first_notes_without_vocabulary = course["chunk_count"]
                    self.study_service.set_vocabulary(
                        course_id=course_id,
                        terms=self.study_service.extract_vocabulary(text=course["transcript"]),
                    )

            if audios:
                if first_notes_without_vocabulary and course.get("vocabulary"):
                    for chunk_index in range(first_notes_without_vocabulary):
                        course["chunk_summaries"][chunk_index] = None

                job["step"] = "notes et résumé du cours"
                self.study_service.summarize_course(course_id=course_id, paced=True, progress=self.update_progress(job=job))

            if pdf_groups:
                job["step"] = "lecture du PDF et résumé global"
                self.study_service.process_pdf(course_id=course_id, pdf_groups=pdf_groups)

                pdf = self.study_service.get_pdf_status(course_id=course_id)

                if pdf["status"] == "error":
                    raise RuntimeError("PDF : " + str(pdf["error"]))

            job["step"] = "terminé"
            job["status"] = "done"

        except Exception as error:
            job["status"] = "error"
            job["error"] = str(error)


    def update_progress(self, job):

        def update(done_chunks):
            job["notes_done"] = done_chunks

        return update


    def get_status(self, course_id):

        job = self.jobs.get(course_id)

        if job is None:
            return None

        pdf = self.study_service.get_pdf_status(course_id=course_id)
        course = self.study_service.courses.get(course_id)

        return {
            "course_id": course_id,
            **job,
            "chunk_count": course["chunk_count"] if course else 0,
            "vocabulary": course.get("vocabulary", []) if course else [],
            "audio": self.long_audio_processor.get_status(course_id=course_id),
            "pdf": {key: value for key, value in pdf.items() if key != "summary"} if pdf is not None else None,
        }