class LessonProcessor:
    def __init__(self, study_service, long_audio_processor):
        self.study_service = study_service
        self.long_audio_processor = long_audio_processor
        self.jobs = {}


    def process(self, course_id, audio_file_name, audio_bytes, pdf_groups):

        job = {"status": "processing", "step": "démarrage", "error": None}
        self.jobs[course_id] = job

        try:
            if audio_bytes:
                job["step"] = "transcription de l'audio"
                self.long_audio_processor.process(
                    course_id=course_id,
                    audio_file_name=audio_file_name,
                    audio_bytes=audio_bytes,
                )

                audio_job = self.long_audio_processor.jobs[course_id]

                if audio_job["status"] == "error":
                    raise RuntimeError("Audio : " + str(audio_job["error"]))

                job["step"] = "résumé du cours"
                self.study_service.summarize_course(course_id=course_id, paced=True)

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


    def get_status(self, course_id):

        job = self.jobs.get(course_id)

        if job is None:
            return None

        pdf = self.study_service.get_pdf_status(course_id=course_id)

        return {
            "course_id": course_id,
            **job,
            "audio": self.long_audio_processor.get_status(course_id=course_id),
            "pdf": {key: value for key, value in pdf.items() if key != "summary"} if pdf is not None else None,
        }