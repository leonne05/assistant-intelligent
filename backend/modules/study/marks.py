import re
from datetime import datetime


class CourseMarks:
    def __init__(self, study_service):
        self.study_service = study_service
        self.max_length = 500
        self.max_marks = 50


    @staticmethod
    def build_section(marks):

        if not marks:
            return ""

        lines = [f"- **{mark['text']}**" for mark in marks]

        return "## Passages marqués par toi\n\n" + "\n".join(lines)


    @staticmethod
    def apply_bold(text, marks):

        for mark in marks:
            words = mark["text"].split()

            if not words:
                continue

            pattern = re.compile(r"\s+".join(re.escape(word) for word in words), re.IGNORECASE)

            def bold(match):
                before = match.string[max(0, match.start() - 2):match.start()]
                after = match.string[match.end():match.end() + 2]

                if before == "**" and after == "**":
                    return match.group(0)

                return f"**{match.group(0)}**"

            text = pattern.sub(bold, text)

        return text


    @staticmethod
    def apply(text, marks):

        if not marks:
            return text

        marked_text = CourseMarks.apply_bold(text=text, marks=marks)

        return marked_text.rstrip() + "\n\n" + CourseMarks.build_section(marks=marks)


    def add_mark(self, course_id, text):

        if course_id not in self.study_service.courses:
            return None

        text = " ".join((text or "").split())

        if not text:
            raise ValueError("Écris le passage que tu veux marquer.")

        if len(text) > self.max_length:
            raise ValueError("Le passage est trop long : marque une phrase ou deux, pas un paragraphe.")

        course = self.study_service.courses[course_id]
        marks = course.setdefault("marks", [])

        if any(mark["text"].lower() == text.lower() for mark in marks):
            raise ValueError("Ce passage est déjà marqué.")

        if len(marks) >= self.max_marks:
            raise ValueError("Tu as déjà 50 passages marqués dans ce cours : supprime-en avant d'en ajouter.")

        number = max([int(mark["mark_id"][1:]) for mark in marks] + [0]) + 1
        mark = {
            "mark_id": f"m{number}",
            "text": text,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        marks.append(mark)
        self.study_service.save_course(course_id=course_id)

        return mark


    def list_marks(self, course_id):

        if course_id not in self.study_service.courses:
            return None

        return self.study_service.courses[course_id].get("marks", [])


    def delete_mark(self, course_id, mark_id):

        if course_id not in self.study_service.courses:
            return None

        marks = self.study_service.courses[course_id].get("marks", [])
        remaining = [mark for mark in marks if mark["mark_id"] != mark_id]

        if len(remaining) == len(marks):
            return False

        self.study_service.courses[course_id]["marks"] = remaining
        self.study_service.save_course(course_id=course_id)

        return True


    def get_marked_summary(self, course_id):

        if course_id not in self.study_service.courses:
            return None

        course = self.study_service.courses[course_id]
        pdf = course["pdf"]
        summary = pdf["summary"] if pdf is not None and pdf["summary"] else course["summary"]

        if not summary:
            raise ValueError("Ce cours n'a pas encore de résumé : lance d'abord le résumé du cours.")

        return {
            "course_id": course_id,
            "summary": self.apply(text=summary, marks=course.get("marks", [])),
            "mark_count": len(course.get("marks", [])),
        }