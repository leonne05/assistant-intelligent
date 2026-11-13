import csv
import io
import json
import os
import re
from datetime import date, datetime

from modules.module6_llm import LlmClient


class FlashcardManager:
    def __init__(self, study_service, subject_manager, study_exporter):
        self.study_service = study_service
        self.subject_manager = subject_manager
        self.study_exporter = study_exporter
        self.flashcards_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_flashcards.txt")
        )

        self.max_question_length = 300
        self.max_answer_length = 600
        self.formats = {
            "csv": {"extension": "csv", "media_type": "text/csv; charset=utf-8"},
            "pdf": self.study_exporter.formats["pdf"],
            "docx": self.study_exporter.formats["docx"],
            "md": self.study_exporter.formats["md"],
        }


    def parse_cards(self, answer):

        start = answer.find("[")
        end = answer.rfind("]")

        if start == -1 or end == -1:
            return []

        try:
            raw_cards = json.loads(answer[start:end + 1])
        except ValueError:
            return []

        cards = []
        seen_questions = set()

        for raw_card in raw_cards:
            if not isinstance(raw_card, dict):
                continue

            question = raw_card.get("question")
            answer_text = raw_card.get("answer")

            if not isinstance(question, str) or not isinstance(answer_text, str):
                continue

            question = " ".join(question.split())[:self.max_question_length]
            answer_text = " ".join(answer_text.split())[:self.max_answer_length]

            if not question or not answer_text or question.lower() in seen_questions:
                continue

            seen_questions.add(question.lower())

            cards.append({
                "question": question,
                "answer": answer_text,
                "topic": str(raw_card.get("topic") or "général")[:60],
                "marked": raw_card.get("marked") is True,
            })

        return cards


    def generate(self, course_id, card_count=10):

        if course_id not in self.study_service.courses:
            return None

        course = self.study_service.courses[course_id]
        material = self.study_service.get_quiz_material(course=course)

        if len(material.strip()) < self.study_service.min_quiz_chars:
            raise ValueError("Ce cours n'a pas encore assez de contenu pour faire des fiches.")

        answer = self.study_service.llm_client.ask_paced(
            context=self.flashcards_context,
            text_interaction=f"Nombre de fiches demandé : {card_count}\n\nContenu du cours :\n{material}",
        )

        cards = self.parse_cards(answer=answer)[:card_count]

        if not cards:
            raise RuntimeError("Les fiches générées sont inutilisables, réessaie.")

        created_at = datetime.now().isoformat(timespec="seconds")

        for number, card in enumerate(cards, start=1):
            card["card_id"] = f"c{number}"
            card["created_at"] = created_at

        course["flashcards"] = cards
        self.study_service.save_course(course_id=course_id)

        return {"course_id": course_id, "card_count": len(cards), "cards": cards}


    def get_deck(self, course_id):

        if course_id not in self.study_service.courses:
            return None

        cards = self.study_service.courses[course_id].get("flashcards", [])

        return {"course_id": course_id, "card_count": len(cards), "cards": cards}


    def delete_card(self, course_id, card_id):

        if course_id not in self.study_service.courses:
            return None

        cards = self.study_service.courses[course_id].get("flashcards", [])
        remaining = [card for card in cards if card["card_id"] != card_id]

        if len(remaining) == len(cards):
            return False

        self.study_service.courses[course_id]["flashcards"] = remaining
        self.study_service.save_course(course_id=course_id)

        return True


    def delete_deck(self, course_id):

        if course_id not in self.study_service.courses:
            return None

        count = len(self.study_service.courses[course_id].get("flashcards", []))
        self.study_service.courses[course_id]["flashcards"] = []
        self.study_service.save_course(course_id=course_id)

        return count


    def get_subject_deck(self, subject):

        subject_name = self.subject_manager.find_subject(name=subject)

        if subject_name is None:
            return None

        lessons = []

        for lesson_number, course_id, course in self.subject_manager.get_lessons(subject_name=subject_name):
            cards = course.get("flashcards", [])

            if cards:
                lessons.append({"lesson_number": lesson_number, "course_id": course_id, "cards": cards})

        return {
            "subject": subject_name,
            "card_count": sum(len(lesson["cards"]) for lesson in lessons),
            "lessons": lessons,
        }


    def make_tag(self, text):
        return re.sub(r"[^\w-]+", "_", text.strip().lower()).strip("_") or "general"


    def build_csv(self, groups):

        buffer = io.StringIO()
        buffer.write("#separator:comma\n#html:false\n#tags column:3\n")
        writer = csv.writer(buffer, lineterminator="\n")

        for label, cards in groups:
            for card in cards:
                tags = f"{self.make_tag(text=label)} {self.make_tag(text=card['topic'])}"
                writer.writerow([card["question"], card["answer"], tags])

        return buffer.getvalue().encode("utf-8")


    def build_markdown(self, title, groups):

        parts = [f"# Fiches de révision - {title}"]
        number = 0

        for label, cards in groups:
            parts.append(f"## {label}")

            for card in cards:
                number += 1
                star = " (passage marqué)" if card["marked"] else ""
                parts.append(f"### Fiche {number} - {card['topic']}{star}")
                parts.append(f"**Question.** {card['question']}")
                parts.append(f"**Réponse.** {card['answer']}")

        parts.append(f"Document généré par JARVIS (module Études) le {date.today().strftime('%d/%m/%Y')}.")

        return "\n\n".join(parts)


    def export(self, title, groups, file_format):

        if file_format not in self.formats:
            raise ValueError("Format inconnu : choisis csv, pdf, docx ou md.")

        groups = [(label, cards) for label, cards in groups if cards]

        if not groups:
            raise ValueError("Il n'y a pas encore de fiches : génère-les d'abord.")

        if file_format == "csv":
            data = self.build_csv(groups=groups)
        elif file_format == "md":
            data = self.build_markdown(title=title, groups=groups).encode("utf-8")
        else:
            blocks = self.study_exporter.parse_markdown(markdown=self.build_markdown(title=title, groups=groups))

            if file_format == "pdf":
                data = self.study_exporter.build_pdf(blocks=blocks, title=f"Fiches {title}")
            else:
                data = self.study_exporter.build_docx(blocks=blocks)

        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_") or "cours"
        file_info = self.formats[file_format]

        return {
            "file_name": f"jarvis_{safe_name}_fiches.{file_info['extension']}",
            "media_type": file_info["media_type"],
            "data": data,
        }


    def export_course(self, course_id, file_format):

        deck = self.get_deck(course_id=course_id)

        if deck is None:
            return None

        return self.export(title=course_id, groups=[(course_id, deck["cards"])], file_format=file_format)


    def export_subject(self, subject, file_format):

        deck = self.get_subject_deck(subject=subject)

        if deck is None:
            return None

        groups = [
            (f"Leçon {lesson['lesson_number']} ({lesson['course_id']})", lesson["cards"])
            for lesson in deck["lessons"]
        ]

        return self.export(title=deck["subject"], groups=groups, file_format=file_format)