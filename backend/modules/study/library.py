import re
from datetime import datetime


class StudyLibrary:
    def __init__(self, study_service, subject_manager, revision_planner, study_exporter):
        self.study_service = study_service
        self.subject_manager = subject_manager
        self.revision_planner = revision_planner
        self.study_exporter = study_exporter


    def record_correction(self, quiz_id, correction):

        quiz = self.study_service.memory.load_quiz(quiz_id=quiz_id)

        if quiz is None:
            return

        quiz["correction"] = correction
        quiz["corrected_at"] = datetime.now().isoformat(timespec="seconds")

        self.study_service.memory.save_quiz(quiz_id=quiz_id, course_id=quiz["course_id"], quiz=quiz)


    def describe_quiz(self, row):

        quiz = row["quiz"]
        course = self.study_service.courses.get(row["course_id"])
        correction = quiz.get("correction")

        return {
            "quiz_id": row["quiz_id"],
            "course_id": row["course_id"],
            "subject": course.get("subject") if course else None,
            "lesson_number": course.get("lesson_number") if course else None,
            "question_count": len(quiz["questions"]),
            "created_at": row["created_at"],
            "status": "corrigé" if quiz.get("corrected") else "à faire",
            "score": correction["score"] if correction else None,
            "total": correction["total"] if correction else None,
            "score_percent": correction["score_percent"] if correction else None,
        }


    def list_quizzes(self, subject=None, course_id=None):

        subject_name = None

        if subject:
            subject_name = self.subject_manager.find_subject(name=subject)

            if subject_name is None:
                return []

        quizzes = []

        for row in self.study_service.memory.list_quizzes():
            description = self.describe_quiz(row=row)

            if course_id and row["course_id"] != course_id:
                continue

            if subject_name and description["subject"] != subject_name:
                continue

            quizzes.append(description)

        return quizzes


    def get_quiz(self, quiz_id):

        quiz = self.study_service.memory.load_quiz(quiz_id=quiz_id)

        if quiz is None:
            return None

        row = next((row for row in self.study_service.memory.list_quizzes() if row["quiz_id"] == quiz_id), None)
        description = self.describe_quiz(row=row)

        if not quiz.get("corrected"):
            return {**description, **self.study_service.get_public_quiz(quiz=quiz)}

        correction = quiz.get("correction")

        if correction is None:
            return {**description, "message": "Ce quiz a été corrigé avant l'ajout de la bibliothèque : le détail n'a pas été gardé."}

        return {**description, "corrected_at": quiz.get("corrected_at"), "correction": correction}


    def delete_quiz(self, quiz_id):
        return self.study_service.memory.delete_quiz(quiz_id=quiz_id)


    def build_quiz_markdown(self, quiz_id, quiz, row):

        correction = quiz.get("correction")

        if correction is None:
            raise ValueError("Ce quiz n'a pas de correction enregistrée : corrige-le d'abord pour pouvoir le télécharger.")

        description = self.describe_quiz(row=row)
        where = f"{description['subject']}, leçon {description['lesson_number']}" if description["subject"] else f"cours {row['course_id']}"
        created = datetime.fromisoformat(row["created_at"]).strftime("%d/%m/%Y")

        lines = [
            f"# Quiz : {where}",
            "",
            f"Passé le {created}. Score : {correction['score']} sur {correction['total']} ({correction['score_percent']} %). "
            "Document généré par JARVIS (module Études).",
            "",
        ]

        if correction["to_review"]:
            lines += ["**À revoir :** " + ", ".join(correction["to_review"]) + ".", ""]

        for result, question in zip(correction["results"], quiz["questions"]):
            lines += [f"## Question {result['number']}", "", result["question"], ""]

            for index, choice in enumerate(question["choices"]):
                letter = "ABCD"[index]
                marks = []

                if choice == result["your_answer"]:
                    marks.append("ta réponse")

                if choice == result["correct_answer"]:
                    marks.append("bonne réponse")

                suffix = f" **({', '.join(marks)})**" if marks else ""
                lines.append(f"- {letter}. {choice}{suffix}")

            if result["your_answer"] is None:
                lines += ["", "Tu n'as pas répondu à cette question."]

            lines += ["", f"Explication : {result['explanation']}", f"Notion : {result['topic']}", ""]

        return "\n".join(lines)


    def export_quiz(self, quiz_id, file_format):

        row = next((row for row in self.study_service.memory.list_quizzes() if row["quiz_id"] == quiz_id), None)

        if row is None:
            return None

        if file_format not in self.study_exporter.formats:
            raise ValueError("Format inconnu : choisis pdf, docx ou md.")

        markdown = self.build_quiz_markdown(quiz_id=quiz_id, quiz=row["quiz"], row=row)

        if file_format == "md":
            data = markdown.encode("utf-8")
        else:
            blocks = self.study_exporter.parse_markdown(markdown=markdown)

            if file_format == "pdf":
                data = self.study_exporter.build_pdf(blocks=blocks, title=f"Quiz {quiz_id}")
            else:
                data = self.study_exporter.build_docx(blocks=blocks)

        file_info = self.study_exporter.formats[file_format]

        return {
            "file_name": f"jarvis_quiz_{re.sub(r'[^A-Za-z0-9_-]+', '_', row['course_id']).strip('_')}_{quiz_id}.{file_info['extension']}",
            "media_type": file_info["media_type"],
            "data": data,
        }


    def get_library(self, subject=None):

        subjects = []

        for subject_name in self.study_service.memory.list_subjects():
            if subject and self.subject_manager.find_subject(name=subject) != subject_name:
                continue

            lessons = self.subject_manager.get_lessons(subject_name=subject_name)

            subjects.append({
                "name": subject_name,
                "lessons": [
                    self.subject_manager.describe_lesson(lesson_number=number, course_id=course_id, course=course)
                    for number, course_id, course in lessons
                ],
                "quizzes": self.list_quizzes(subject=subject_name),
                "revision_plans": self.revision_planner.list_plans(subject=subject_name),
            })

        return {"subjects": subjects}