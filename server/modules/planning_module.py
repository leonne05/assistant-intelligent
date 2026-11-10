from modules.base_module import BaseModule


class PlanningModule(BaseModule):
    """Module Planning (Mariam) — VERSION DÉMO avec un agenda fictif."""

    name = "Planning"
    owner = "Mariam"

    EVENTS = [
        {"title": "Réunion d'équipe", "start": "10:00", "end": "11:00"},
        {"title": "Déjeuner avec Sarah", "start": "12:30", "end": "13:30"},
        {"title": "Rendez-vous client", "start": "14:00", "end": "15:00"},
        {"title": "Point projet", "start": "14:30", "end": "15:00"},
    ]

    def __init__(self):
        super().__init__()
        self.actions = {
            "GENERATE_BRIEFING": self.generate_briefing,
            "GET_SCHEDULE": self.get_schedule,
        }

    @staticmethod
    def to_minutes(hour):
        hours, minutes = hour.split(":")
        return int(hours) * 60 + int(minutes)

    @staticmethod
    def spoken_hour(hour):
        return hour.replace(":00", "h").replace(":", "h")

    def find_conflict(self):
        for previous, current in zip(self.EVENTS, self.EVENTS[1:]):
            if self.to_minutes(current["start"]) < self.to_minutes(previous["end"]):
                return previous, current
        return None

    def generate_briefing(self, entities, text_interaction):
        first_event = self.EVENTS[0]
        response = (
            f"Tu as {len(self.EVENTS)} rendez-vous aujourd'hui. "
            f"Le premier est {first_event['title']} à {self.spoken_hour(first_event['start'])}."
        )

        conflict = self.find_conflict()
        if conflict:
            response += f" Attention, {conflict[0]['title']} chevauche {conflict[1]['title']}."
        return response

    def get_schedule(self, entities, text_interaction):
        listing = ", ".join(f"{event['title']} à {self.spoken_hour(event['start'])}" for event in self.EVENTS)
        return f"Voici ton programme : {listing}."