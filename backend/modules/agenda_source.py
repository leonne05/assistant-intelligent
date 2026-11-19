from datetime import datetime
import uuid


class AgendaSource:
    """Classe mère : elle décrit ce que tout agenda doit savoir faire, elle ne s'utilise pas directement.

    Chaque agenda (l'agenda simulé d'aujourd'hui, celui de Mariam demain) hérite de cette
    classe et remplit les deux méthodes. Un événement est un dictionnaire :
    {"event_id", "title", "start", "end"} avec des dates au format AAAA-MM-JJTHH:MM.
    """

    def __init__(self):
        self.name = "agenda"


    def get_events(self, day):
        raise NotImplementedError("Cet agenda ne sait pas encore lister ses événements.")


    def add_event(self, title, start, end):
        raise NotImplementedError("Cet agenda ne sait pas encore ajouter un événement.")


    def delete_event(self, event_id):
        raise NotImplementedError("Cet agenda ne sait pas encore supprimer un événement.")


class SimulatedAgenda(AgendaSource):
    """Agenda fictif gardé en mémoire, pour tester en attendant l'agenda de Mariam."""

    def __init__(self):
        super().__init__()
        self.name = "agenda simulé"
        self.events = []


    def add_event(self, title, start, end):

        title = " ".join(title.split())[:120]

        if not title:
            raise ValueError("L'événement doit avoir un titre.")

        start_time = datetime.fromisoformat(start)
        end_time = datetime.fromisoformat(end)

        if end_time <= start_time:
            raise ValueError("La fin de l'événement doit être après son début.")

        event = {
            "event_id": uuid.uuid4().hex[:8],
            "title": title,
            "start": start_time.isoformat(timespec="minutes"),
            "end": end_time.isoformat(timespec="minutes"),
        }
        self.events.append(event)

        return event


    def get_events(self, day):

        events_of_day = []

        for event in self.events:
            starts_on_day = datetime.fromisoformat(event["start"]).date() <= day
            ends_on_day = datetime.fromisoformat(event["end"]).date() >= day

            if starts_on_day and ends_on_day:
                events_of_day.append(event)

        return sorted(events_of_day, key=lambda event: event["start"])


    def delete_event(self, event_id):

        for event in self.events:
            if event["event_id"] == event_id:
                self.events.remove(event)
                return True

        return False