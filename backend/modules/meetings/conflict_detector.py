from datetime import datetime, timedelta


class ConflictDetector:
    """Cherche ce qui se passe en même temps qu'une réunion (agenda et autres réunions)."""

    def __init__(self, agenda_source, meetings_service):
        self.agenda_source = agenda_source
        self.meetings_service = meetings_service

        self.day_start_hour = 8
        self.day_end_hour = 19


    @staticmethod
    def overlaps(start_a, end_a, start_b, end_b):
        return start_a < end_b and start_b < end_a


    def get_busy_periods(self, day, ignore_meeting_id=None):

        periods = []
        own_event_id = None

        if ignore_meeting_id is not None and ignore_meeting_id in self.meetings_service.meetings:
            own_event_id = self.meetings_service.meetings[ignore_meeting_id].get("agenda_event_id")

        for event in self.agenda_source.get_events(day=day):

            if event["event_id"] == own_event_id:
                continue

            periods.append({
                "title": event["title"],
                "start": datetime.fromisoformat(event["start"]),
                "end": datetime.fromisoformat(event["end"]),
                "source": self.agenda_source.name,
            })

        for meeting in self.meetings_service.meetings.values():

            if meeting["meeting_id"] == ignore_meeting_id or not meeting.get("start"):
                continue

            start = datetime.fromisoformat(meeting["start"])
            end = start + timedelta(minutes=meeting["duration_minutes"])

            if start.date() == day:
                periods.append({"title": meeting["title"], "start": start, "end": end, "source": "réunion JARVIS"})

        return sorted(periods, key=lambda period: period["start"])


    def find_conflicts(self, start, end, ignore_meeting_id=None):

        conflicts = []

        for period in self.get_busy_periods(day=start.date(), ignore_meeting_id=ignore_meeting_id):
            if self.overlaps(start, end, period["start"], period["end"]):
                conflicts.append({
                    "title": period["title"],
                    "start": period["start"].isoformat(timespec="minutes"),
                    "end": period["end"].isoformat(timespec="minutes"),
                    "source": period["source"],
                })

        return conflicts


    def find_free_slot(self, day, duration_minutes, earliest=None, ignore_meeting_id=None):
        """Premier créneau libre, à partir de `earliest` (ou de 8h), avant 19h. Renvoie None s'il n'y en a pas."""

        slot_start = datetime(day.year, day.month, day.day, self.day_start_hour)

        if earliest is not None:
            slot_start = max(slot_start, earliest)

        day_end = datetime(day.year, day.month, day.day, self.day_end_hour)
        duration = timedelta(minutes=duration_minutes)

        for period in self.get_busy_periods(day=day, ignore_meeting_id=ignore_meeting_id):
            if slot_start + duration <= period["start"]:
                break

            slot_start = max(slot_start, period["end"])

        if slot_start + duration > day_end:
            return None

        return {
            "start": slot_start.isoformat(timespec="minutes"),
            "end": (slot_start + duration).isoformat(timespec="minutes"),
        }