from datetime import date


class RevisionOfferManager:
    def __init__(self, study_service, revision_planner):
        self.study_service = study_service
        self.revision_planner = revision_planner
        self.offered_types = ["examen", "devoir"]


    def is_offerable(self, event):

        if event["status"] != "approved" or event["type"] not in self.offered_types:
            return False

        if event.get("revision") is not None:
            return False

        return date.fromisoformat(event["date"]) > date.today()


    def build_offer(self, course_id, course, event):

        subject = course.get("subject")
        event_date = date.fromisoformat(event["date"])
        what = "un examen" if event["type"] == "examen" else "un devoir"
        where = f" en {subject}" if subject else ""

        return {
            "course_id": course_id,
            "event_id": event["id"],
            "event_type": event["type"],
            "title": event["title"],
            "date": event["date"],
            "subject": subject,
            "needs_subject": subject is None,
            "question": (
                f"Tu as {what}{where} le {self.study_service.format_date(event_date)} (« {event['title']} »). "
                "Veux-tu que je te prépare un plan de révision ?"
            ),
        }


    def get_offer(self, course_id, event):

        course = self.study_service.courses.get(course_id)

        if course is None or not self.is_offerable(event=event):
            return None

        return self.build_offer(course_id=course_id, course=course, event=event)


    def list_offers(self):

        offers = []
        seen = set()

        for course_id, course in self.study_service.courses.items():
            for event in course["events"]:
                if not self.is_offerable(event=event):
                    continue

                key = (course.get("subject") or course_id, event["date"])

                if key in seen:
                    continue

                seen.add(key)
                offers.append(self.build_offer(course_id=course_id, course=course, event=event))

        offers.sort(key=lambda offer: offer["date"])

        return offers


    def mark_same_exam(self, subject, event_date, revision, plan_id):

        if not subject:
            return

        for course_id, course in self.study_service.courses.items():
            if course.get("subject") != subject:
                continue

            changed = False

            for event in course["events"]:
                if event["date"] == event_date and event["type"] in self.offered_types and event.get("revision") is None:
                    event["revision"] = revision
                    event["plan_id"] = plan_id
                    changed = True

            if changed:
                self.study_service.save_course(course_id=course_id)


    def answer(self, course_id, event_id, accept, minutes_per_day):

        course = self.study_service.courses.get(course_id)

        if course is None:
            return None

        event = next((event for event in course["events"] if event["id"] == event_id), None)

        if event is None:
            return None

        if event["status"] != "approved":
            raise ValueError("Cet événement n'est pas validé : valide-le d'abord pour que je te propose un plan.")

        if event.get("revision") is not None:
            raise ValueError("Tu as déjà répondu à cette proposition de plan de révision.")

        if not accept:
            self.mark_same_exam(subject=course.get("subject"), event_date=event["date"], revision="declined", plan_id=None)
            event["revision"] = "declined"
            self.study_service.save_course(course_id=course_id)

            return {"revision": "declined", "plan": None}

        if not course.get("subject"):
            raise ValueError("Range d'abord ce cours dans une matière (PATCH /study/courses/{id}/subject).")

        plan = self.revision_planner.prepare(
            subject=course["subject"],
            exam_date_text=event["date"],
            minutes_per_day=minutes_per_day,
        )

        if plan is None:
            raise ValueError("Matière introuvable.")

        self.mark_same_exam(subject=course["subject"], event_date=event["date"], revision="accepted", plan_id=plan["plan_id"])
        event["revision"] = "accepted"
        event["plan_id"] = plan["plan_id"]
        self.study_service.save_course(course_id=course_id)

        return {"revision": "accepted", "plan": plan}