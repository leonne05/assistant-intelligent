import os

from modules.module6_llm import LlmClient


class Explainer:
    def __init__(self, study_service, subject_manager):
        self.study_service = study_service
        self.subject_manager = subject_manager
        self.explain_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_explain.txt")
        )
        self.check_context = LlmClient.read_file(
            file_path=os.path.join(os.path.dirname(__file__), "context_explain_check.txt")
        )

        self.levels = ["simple", "plus_simple", "approfondi"]
        self.max_topic_length = 200
        self.max_answer_length = 1500
        self.max_extracts = 4
        self.question_title = "## Question pour vérifier"


    def get_course_ids(self, course_id=None, subject=None):

        if course_id:
            if course_id not in self.study_service.courses:
                raise ValueError("Cours introuvable.")

            return [course_id]

        if subject:
            subject_name = self.subject_manager.find_subject(name=subject)

            if subject_name is None:
                raise ValueError("Matière introuvable.")

            return [course_id for number, course_id, course in self.subject_manager.get_lessons(subject_name=subject_name)]

        return list(self.study_service.courses.keys())


    def find_extracts(self, topic, course_ids):

        keywords = self.study_service.get_keywords(question=topic)

        if not keywords:
            return []

        scored_extracts = []

        for course_id in course_ids:
            course = self.study_service.courses[course_id]

            for note in self.study_service.get_course_notes(course_id=course_id, course=course):
                stems = [word[:5] for word in self.study_service.get_words(note["content"])]
                matches = [stem for stem in stems if stem in keywords]

                if not matches:
                    continue

                score = len(set(matches)) * 5 + len(matches)
                scored_extracts.append((score, {**note, "course_id": course_id}))

        scored_extracts.sort(key=lambda scored_extract: scored_extract[0], reverse=True)

        return [extract for score, extract in scored_extracts[:self.max_extracts]]


    def clean_topic(self, topic):

        topic = (topic or "").strip()

        if not topic:
            raise ValueError("Dis-moi quelle notion tu veux que je t'explique.")

        if len(topic) > self.max_topic_length:
            raise ValueError("La notion est trop longue : résume-la en une phrase.")

        return topic


    def explain(self, topic, level="simple", course_id=None, subject=None):

        topic = self.clean_topic(topic=topic)

        if level not in self.levels:
            raise ValueError("Le niveau doit être simple, plus_simple ou approfondi.")

        extracts = self.find_extracts(topic=topic, course_ids=self.get_course_ids(course_id=course_id, subject=subject))

        text_interaction = (
            f"Niveau demandé : {level}\n"
            f"Notion à expliquer : {topic}\n\n"
            + self.study_service.format_notes(notes=extracts)
        )

        answer = self.llm_answer(context=self.explain_context, text_interaction=text_interaction)

        if self.question_title in answer:
            explanation, check_question = answer.split(self.question_title, 1)
        else:
            explanation, check_question = answer, ""

        return {
            "topic": topic,
            "level": level,
            "explanation": explanation.strip(),
            "check_question": check_question.strip() or None,
            "sources": [extract["label"] for extract in extracts],
        }


    def llm_answer(self, context, text_interaction):
        return self.study_service.llm_client.ask(context=context, text_interaction=text_interaction)


    def check(self, topic, question, answer, course_id=None, subject=None):

        topic = self.clean_topic(topic=topic)
        question = (question or "").strip()
        answer = (answer or "").strip()

        if not question:
            raise ValueError("Il manque la question à laquelle tu réponds.")

        if len(answer) > self.max_answer_length:
            raise ValueError("Ta réponse est trop longue : une ou deux phrases suffisent.")

        extracts = self.find_extracts(topic=topic, course_ids=self.get_course_ids(course_id=course_id, subject=subject))

        text_interaction = (
            f"Notion : {topic}\n"
            f"Question posée : {question}\n\n"
            + self.study_service.format_notes(notes=extracts)
            + f"\n\n## Réponse de l'étudiant\n\n{answer or '(aucune réponse)'}"
        )

        reply = self.llm_answer(context=self.check_context, text_interaction=text_interaction).strip()
        first_line, _, feedback = reply.partition("\n")
        verdict = "partiel"

        for possible_verdict in ("juste", "partiel", "faux"):
            if first_line.lower().replace(" ", "").startswith(f"verdict:{possible_verdict}"):
                verdict = possible_verdict

        recorded_course_id = course_id or (extracts[0]["course_id"] if extracts else None)

        if recorded_course_id:
            self.study_service.memory.save_attempts(
                quiz_id="explique-moi",
                course_id=recorded_course_id,
                results=[(topic.lower()[:60], verdict == "juste")],
            )

        return {"topic": topic, "verdict": verdict, "feedback": feedback.strip() or reply}