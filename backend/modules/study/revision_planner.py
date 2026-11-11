import hashlib
import math
import os
import re
import uuid
from datetime import date, datetime, timedelta

from modules.module6_llm import LlmClient


class RevisionPlanner:
    def __init__(self, study_service, subject_manager, study_exporter):
        self.study_service = study_service
        self.subject_manager = subject_manager
        self.study_exporter = study_exporter
        self.digest_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_subject_digest.txt")
        )

        self.min_minutes = 15
        self.max_minutes = 240
        self.max_days = 120
        self.recall_minutes = 10
        self.quiz_minutes = 15
        self.max_weak_topics = 6

        for plan in self.study_service.memory.list_plans():
            if plan["status"] == "processing":
                plan["status"] = "error"
                plan["error"] = "Traitement interrompu par un redémarrage du serveur : relance le plan."
                self.study_service.memory.save_plan(plan_id=plan["plan_id"], subject=plan["subject"], plan=plan)


    def parse_date(self, text, label):

        try:
            return date.fromisoformat((text or "").strip())
        except ValueError:
            raise ValueError(f"{label} doit être au format AAAA-MM-JJ, par exemple 2026-12-15.")


    def get_lesson_material(self, course):

        pdf = course["pdf"]

        if pdf is not None and pdf["summary"]:
            return pdf["summary"]

        return course["summary"]


    def prepare(self, subject, exam_date_text, minutes_per_day, start_date_text=None):

        subject_name = self.subject_manager.find_subject(name=subject)

        if subject_name is None:
            return None

        exam_date = self.parse_date(text=exam_date_text, label="La date de l'examen")
        start_date = self.parse_date(text=start_date_text, label="La date de début") if start_date_text else date.today()

        if exam_date <= start_date:
            raise ValueError("La date de l'examen doit être après le début du plan.")

        if (exam_date - start_date).days > self.max_days:
            raise ValueError("L'examen est trop loin : un plan couvre au maximum 120 jours.")

        if not self.min_minutes <= minutes_per_day <= self.max_minutes:
            raise ValueError("La durée par jour doit être comprise entre 15 et 240 minutes.")

        lessons = self.subject_manager.get_lessons(subject_name=subject_name)

        if not lessons:
            raise ValueError("Cette matière n'a aucune leçon : ajoute d'abord tes leçons.")

        if not any(self.get_lesson_material(course=course) for number, course_id, course in lessons):
            raise ValueError("Aucune leçon de cette matière n'a encore de résumé : attends la fin du traitement des leçons.")

        plan = {
            "plan_id": uuid.uuid4().hex[:8],
            "subject": subject_name,
            "status": "processing",
            "exam_date": exam_date.isoformat(),
            "start_date": start_date.isoformat(),
            "minutes_per_day": minutes_per_day,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "error": None,
            "warning": None,
            "skipped_lessons": [],
            "digest": [],
            "days": [],
        }

        self.study_service.memory.save_plan(plan_id=plan["plan_id"], subject=subject_name, plan=plan)

        return plan


    def get_digest(self, course_id, course, material):

        fingerprint = hashlib.sha1(material.encode("utf-8")).hexdigest()
        digest = course.get("digest")

        if digest and digest["fingerprint"] == fingerprint:
            return digest["text"]

        text = self.study_service.llm_client.ask_paced(
            context=self.digest_context,
            text_interaction=material,
        ).strip()

        course["digest"] = {"fingerprint": fingerprint, "text": text}
        self.study_service.save_course(course_id=course_id)

        return text


    def get_weak_topics(self, course_id):

        gaps = self.study_service.get_gaps(course_id=course_id)

        return [gap["topic"] for gap in gaps if gap["level"] == "a_retravailler"]


    def process(self, plan_id):

        plan = self.study_service.memory.load_plan(plan_id=plan_id)

        if plan is None:
            return

        try:
            lessons = self.subject_manager.get_lessons(subject_name=plan["subject"])
            entries = []
            weak_topics = {}

            for number, course_id, course in lessons:
                material = self.get_lesson_material(course=course)

                if not material:
                    plan["skipped_lessons"].append(number)
                    continue

                entries.append({
                    "lesson_number": number,
                    "course_id": course_id,
                    "key_points": self.get_digest(course_id=course_id, course=course, material=material),
                })
                weak_topics[course_id] = self.get_weak_topics(course_id=course_id)

            schedule = self.build_schedule(
                entries=entries,
                weak_topics=weak_topics,
                exam_date=date.fromisoformat(plan["exam_date"]),
                start_date=date.fromisoformat(plan["start_date"]),
                minutes_per_day=plan["minutes_per_day"],
            )

            plan["digest"] = entries
            plan["days"] = schedule["days"]
            plan["warning"] = schedule["warning"]
            plan["status"] = "done"

        except Exception as error:
            plan["status"] = "error"
            plan["error"] = str(error)

        self.study_service.memory.save_plan(plan_id=plan_id, subject=plan["subject"], plan=plan)


    def lesson_label(self, entries):

        numbers = [str(entry["lesson_number"]) for entry in entries]

        if len(numbers) == 1:
            return f"la leçon {numbers[0]}"

        return "les leçons " + ", ".join(numbers[:-1]) + " et " + numbers[-1]


    def lesson_title(self, entries, step):

        title = self.lesson_label(entries=entries).replace("la leçon", "Leçon").replace("les leçons", "Leçons")

        return title if step == 0 else f"{title} ({step + 1}e passage)"


    def split_minutes(self, total, parts):

        share = total // parts

        return [share + (total - share * parts if index == parts - 1 else 0) for index in range(parts)]


    def build_study_day(self, entries, step, previous_entries, weak_topics, minutes_per_day):

        sessions = []
        recall = min(self.recall_minutes, minutes_per_day // 5) if previous_entries else 0

        if recall:
            sessions.append({
                "minutes": recall,
                "task": f"Rappel express : sans regarder tes notes, redis à voix haute les points clés de {self.lesson_label(entries=previous_entries)}.",
            })

        remaining = minutes_per_day - recall
        read_total = round(remaining * 0.5)
        quiz_total = remaining - read_total

        for entry, minutes in zip(entries, self.split_minutes(total=read_total, parts=len(entries))):
            label = self.lesson_label(entries=[entry])

            if step == 0:
                task = f"Lis la synthèse de {label}, puis son résumé complet : souligne ce que tu ne sais pas expliquer."
            else:
                task = f"Reprends {label} : refais le résumé de mémoire, puis compare avec la synthèse."

            weak = weak_topics.get(entry["course_id"], [])

            if weak:
                task += " Points faibles à retravailler : " + ", ".join(weak[:4]) + "."

            sessions.append({"minutes": minutes, "task": task})

        sessions.append({
            "minutes": quiz_total,
            "task": f"Quiz : fais un quiz avec JARVIS sur {self.lesson_label(entries=entries)}, puis note les questions ratées.",
        })

        return {"title": self.lesson_title(entries=entries, step=step), "sessions": sessions, "note": None}


    def build_weak_day(self, entries, weak_topics, minutes_per_day):

        topics = []

        for entry in entries:
            for topic in weak_topics.get(entry["course_id"], []):
                if topic not in topics:
                    topics.append(topic)

        topics = topics[:self.max_weak_topics]
        quiz_minutes = min(self.quiz_minutes, minutes_per_day // 3)
        sessions = []

        if topics:
            for topic, minutes in zip(topics, self.split_minutes(total=minutes_per_day - quiz_minutes, parts=len(topics))):
                sessions.append({
                    "minutes": minutes,
                    "task": f"Reprends la notion « {topic} » : relis le passage du cours, puis explique-la avec tes propres mots.",
                })

            sessions.append({
                "minutes": quiz_minutes,
                "task": "Quiz ciblé : demande à JARVIS un quiz centré sur ces notions, puis corrige-toi.",
            })
        else:
            sessions.append({
                "minutes": minutes_per_day,
                "task": "Aucun point faible enregistré pour l'instant : fais un quiz par leçon avec JARVIS pour les repérer, puis retravaille les erreurs.",
            })

        return {"title": "Points faibles", "sessions": sessions, "note": None}


    def build_final_day(self, entries, minutes_per_day):

        read_minutes = round(minutes_per_day * 0.6)
        quiz_minutes = minutes_per_day - read_minutes

        return {
            "title": "Révision générale",
            "sessions": [
                {"minutes": read_minutes, "task": f"Relis les synthèses de {self.lesson_label(entries=entries)}, une par une."},
                {"minutes": quiz_minutes, "task": "Fais un quiz sur chaque leçon, ou un quiz mélangé, puis corrige-toi."},
            ],
            "note": "Veille d'examen : pas de nouvelle notion, et couche-toi tôt.",
        }


    def build_schedule(self, entries, weak_topics, exam_date, start_date, minutes_per_day):

        total_days = (exam_date - start_date).days
        has_weak_day = total_days >= 5
        learning_days = total_days - 1 - (1 if has_weak_day else 0)
        warning = None
        study_days = []

        if total_days == 1:
            warning = "L'examen est demain : une seule journée de révision générale."

        if learning_days >= 1 and entries:
            if learning_days >= len(entries):
                base, extra = divmod(learning_days, len(entries))

                for index, entry in enumerate(entries):
                    for step in range(base + (1 if index < extra else 0)):
                        study_days.append({"entries": [entry], "step": step})
            else:
                per_day = math.ceil(len(entries) / learning_days)

                for start in range(0, len(entries), per_day):
                    study_days.append({"entries": entries[start:start + per_day], "step": 0})

                warning = (
                    f"Il te reste peu de jours pour {len(entries)} leçons : "
                    "plusieurs leçons sont regroupées dans la même journée."
                )

        days = []
        previous_entries = None

        for index, study_day in enumerate(study_days):
            day = self.build_study_day(
                entries=study_day["entries"],
                step=study_day["step"],
                previous_entries=previous_entries,
                weak_topics=weak_topics,
                minutes_per_day=minutes_per_day,
            )
            day["date"] = (start_date + timedelta(days=index)).isoformat()
            days.append(day)
            previous_entries = study_day["entries"]

        if has_weak_day:
            day = self.build_weak_day(entries=entries, weak_topics=weak_topics, minutes_per_day=minutes_per_day)
            day["date"] = (exam_date - timedelta(days=2)).isoformat()
            days.append(day)

        day = self.build_final_day(entries=entries, minutes_per_day=minutes_per_day)
        day["date"] = (exam_date - timedelta(days=1)).isoformat()
        days.append(day)

        return {"days": days, "warning": warning}


    def build_markdown(self, plan):

        exam_date = date.fromisoformat(plan["exam_date"])
        start_date = date.fromisoformat(plan["start_date"])
        created = datetime.fromisoformat(plan["created_at"]).strftime("%d/%m/%Y")

        lines = [
            f"# Plan de révision : {plan['subject']}",
            "",
            f"Examen le {self.study_service.format_date(exam_date)}. "
            f"{len(plan['days'])} jours de travail, {plan['minutes_per_day']} minutes par jour. "
            f"Document généré par JARVIS (module Études) le {created}.",
            "",
        ]

        if plan["warning"]:
            lines += [plan["warning"], ""]

        if plan["skipped_lessons"]:
            numbers = ", ".join(str(number) for number in plan["skipped_lessons"])
            lines += [f"Leçons sans résumé, non incluses dans ce plan : {numbers}.", ""]

        lines += ["## Synthèse de la matière", ""]

        for entry in plan["digest"]:
            lines += [f"### Leçon {entry['lesson_number']}", "", entry["key_points"], ""]

        lines += ["## Planning", ""]

        for day in plan["days"]:
            day_date = date.fromisoformat(day["date"])
            day_number = (day_date - start_date).days + 1

            lines += [f"### Jour {day_number}, {self.study_service.format_date(day_date)} : {day['title']}", ""]
            lines += [f"- **{session['minutes']} min** : {session['task']}" for session in day["sessions"]]

            if day["note"]:
                lines += ["", day["note"]]

            lines.append("")

        return "\n".join(lines)


    def get_plan(self, plan_id):

        plan = self.study_service.memory.load_plan(plan_id=plan_id)

        if plan is None:
            return None

        if plan["status"] == "done":
            plan["text"] = self.build_markdown(plan=plan)

        return plan


    def list_plans(self, subject=None):

        subject_name = None

        if subject:
            subject_name = self.subject_manager.find_subject(name=subject)

            if subject_name is None:
                return []

        return [
            {
                "plan_id": plan["plan_id"],
                "subject": plan["subject"],
                "status": plan["status"],
                "exam_date": plan["exam_date"],
                "minutes_per_day": plan["minutes_per_day"],
                "day_count": len(plan["days"]),
                "created_at": plan["created_at"],
            }
            for plan in self.study_service.memory.list_plans(subject=subject_name)
        ]


    def delete_plan(self, plan_id):
        return self.study_service.memory.delete_plan(plan_id=plan_id)


    def export(self, plan_id, file_format):

        plan = self.study_service.memory.load_plan(plan_id=plan_id)

        if plan is None:
            return None

        if plan["status"] != "done":
            raise ValueError(f"Ce plan n'est pas prêt (statut : {plan['status']}).")

        if file_format not in self.study_exporter.formats:
            raise ValueError("Format inconnu : choisis pdf, docx ou md.")

        markdown = self.build_markdown(plan=plan)

        if file_format == "md":
            data = markdown.encode("utf-8")
        else:
            blocks = self.study_exporter.parse_markdown(markdown=markdown)

            if file_format == "pdf":
                data = self.study_exporter.build_pdf(blocks=blocks, title=f"Plan de révision {plan['subject']}")
            else:
                data = self.study_exporter.build_docx(blocks=blocks)

        safe_subject = re.sub(r"[^A-Za-z0-9_-]+", "_", plan["subject"]).strip("_") or "matiere"
        file_info = self.study_exporter.formats[file_format]

        return {
            "file_name": f"jarvis_plan_{safe_subject}_{plan['exam_date']}.{file_info['extension']}",
            "media_type": file_info["media_type"],
            "data": data,
        }