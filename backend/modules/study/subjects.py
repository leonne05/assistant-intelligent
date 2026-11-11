import re


class SubjectManager:
    def __init__(self, study_service):
        self.study_service = study_service
        self.max_name_length = 60


    def clean_name(self, name):

        name = re.sub(r"\s+", " ", name or "").strip()

        if not name:
            raise ValueError("Le nom de la matière est vide.")

        if len(name) > self.max_name_length:
            raise ValueError("Le nom de la matière dépasse 60 caractères.")

        return name


    def get_key(self, name):
        return self.study_service.normalize_text(text=name).strip()


    def find_subject(self, name):

        key = self.get_key(name=self.clean_name(name=name))

        for subject_name in self.study_service.memory.list_subjects():
            if self.get_key(name=subject_name) == key:
                return subject_name

        return None


    def create_subject(self, name):

        if self.find_subject(name=name) is not None:
            raise ValueError("Cette matière existe déjà.")

        clean_name = self.clean_name(name=name)
        self.study_service.memory.add_subject(name=clean_name)

        return {"name": clean_name}


    def ensure_subject(self, name):

        existing_name = self.find_subject(name=name)

        if existing_name is not None:
            return existing_name

        clean_name = self.clean_name(name=name)
        self.study_service.memory.add_subject(name=clean_name)

        return clean_name


    def get_lessons(self, subject_name):

        lessons = [
            (course.get("lesson_number") or 0, course_id, course)
            for course_id, course in self.study_service.courses.items()
            if course.get("subject") == subject_name
        ]
        lessons.sort(key=lambda lesson: (lesson[0], lesson[1]))

        return lessons


    def describe_lesson(self, lesson_number, course_id, course):

        pdf = course["pdf"]

        return {
            "lesson_number": lesson_number,
            "course_id": course_id,
            "chunk_count": course["chunk_count"],
            "has_summary": course["summary"] is not None,
            "has_pdf": pdf is not None,
            "pdf_status": pdf["status"] if pdf is not None else None,
            "has_global_summary": bool(pdf is not None and pdf["summary"]),
        }


    def list_subjects(self):

        subjects = []

        for subject_name in self.study_service.memory.list_subjects():
            lessons = self.get_lessons(subject_name=subject_name)

            subjects.append({
                "name": subject_name,
                "lesson_count": len(lessons),
                "lessons": [
                    self.describe_lesson(lesson_number=number, course_id=course_id, course=course)
                    for number, course_id, course in lessons
                ],
            })

        unassigned_courses = [
            course_id
            for course_id, course in self.study_service.courses.items()
            if not course.get("subject")
        ]

        return {"subjects": subjects, "unassigned_courses": unassigned_courses}


    def delete_subject(self, name, delete_lessons=False):

        subject_name = self.find_subject(name=name)

        if subject_name is None:
            return None

        lessons = self.get_lessons(subject_name=subject_name)

        if lessons and not delete_lessons:
            raise ValueError(
                f"Cette matière contient {len(lessons)} leçon(s) : "
                "ajoute delete_lessons=true pour tout effacer avec elle."
            )

        for number, course_id, course in lessons:
            self.study_service.delete_course(course_id=course_id)

        self.study_service.memory.delete_subject(name=subject_name)

        return {"name": subject_name, "deleted": True, "deleted_lessons": len(lessons)}


    def next_lesson_number(self, subject_name):

        numbers = [number for number, course_id, course in self.get_lessons(subject_name=subject_name)]

        return max(numbers, default=0) + 1


    def check_lesson_number(self, subject_name, lesson_number, own_course_id=None):

        if lesson_number < 1:
            raise ValueError("Le numéro de leçon doit être 1 ou plus.")

        for number, course_id, course in self.get_lessons(subject_name=subject_name):
            if number == lesson_number and course_id != own_course_id:
                raise ValueError(f"La leçon {lesson_number} existe déjà dans {subject_name}.")


    def build_course_id(self, subject_name, lesson_number):

        slug = re.sub(r"[^a-z0-9]+", "-", self.get_key(name=subject_name)).strip("-") or "matiere"

        return f"{slug}-lecon-{lesson_number}"


    def add_lesson(self, subject, lesson_number=None):

        subject_name = self.ensure_subject(name=subject)

        if not lesson_number:
            lesson_number = self.next_lesson_number(subject_name=subject_name)

        self.check_lesson_number(subject_name=subject_name, lesson_number=lesson_number)

        course_id = self.build_course_id(subject_name=subject_name, lesson_number=lesson_number)

        if course_id in self.study_service.courses:
            raise ValueError(f"Un cours nommé {course_id} existe déjà.")

        course = self.study_service.get_or_create_course(course_id=course_id)
        course["subject"] = subject_name
        course["lesson_number"] = lesson_number
        self.study_service.save_course(course_id=course_id)

        return {"course_id": course_id, "subject": subject_name, "lesson_number": lesson_number}


    def assign_course(self, course_id, subject, lesson_number=None):

        course = self.study_service.courses.get(course_id)

        if course is None:
            return None

        subject_name = self.ensure_subject(name=subject)

        if not lesson_number:
            lesson_number = self.next_lesson_number(subject_name=subject_name)

        self.check_lesson_number(subject_name=subject_name, lesson_number=lesson_number, own_course_id=course_id)

        course["subject"] = subject_name
        course["lesson_number"] = lesson_number
        self.study_service.save_course(course_id=course_id)

        return {"course_id": course_id, "subject": subject_name, "lesson_number": lesson_number}