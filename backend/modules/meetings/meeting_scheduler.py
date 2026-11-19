from datetime import datetime, timedelta

from modules.meetings.meeting_tool import MeetingTool


class MeetingScheduler(MeetingTool):
    """Fixe la date et la durée d'une réunion, signale les conflits et l'ajoute à l'agenda."""

    def __init__(self, meetings_service, agenda_source, conflict_detector):
        super().__init__(meetings_service=meetings_service)
        self.agenda_source = agenda_source
        self.conflict_detector = conflict_detector

        self.min_duration = 5
        self.max_duration = 480
        self.default_duration = 60


    def parse_start(self, start):

        try:
            return datetime.fromisoformat(start.strip()).replace(second=0, microsecond=0)
        except ValueError:
            raise ValueError("La date doit être au format AAAA-MM-JJTHH:MM, par exemple 2026-12-15T14:00.")


    def check_duration(self, duration_minutes):

        if not self.min_duration <= duration_minutes <= self.max_duration:
            raise ValueError(f"La durée doit être entre {self.min_duration} et {self.max_duration} minutes.")


    def describe(self, meeting):

        start = datetime.fromisoformat(meeting["start"])
        end = start + timedelta(minutes=meeting["duration_minutes"])
        conflicts = self.conflict_detector.find_conflicts(
            start=start, end=end, ignore_meeting_id=meeting["meeting_id"]
        )

        free_slot = None

        if conflicts:
            free_slot = self.conflict_detector.find_free_slot(
                day=start.date(),
                duration_minutes=meeting["duration_minutes"],
                earliest=start,
                ignore_meeting_id=meeting["meeting_id"],
            )

        return {
            "meeting_id": meeting["meeting_id"],
            "start": meeting["start"],
            "end": end.isoformat(timespec="minutes"),
            "duration_minutes": meeting["duration_minutes"],
            "in_agenda": meeting.get("in_agenda", False),
            "conflicts": conflicts,
            "free_slot": free_slot,
        }


    def schedule(self, meeting_id, start, duration_minutes=None):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        if duration_minutes is None:
            duration_minutes = meeting.get("duration_minutes", self.default_duration)

        self.check_duration(duration_minutes=duration_minutes)

        new_start = self.parse_start(start=start).isoformat(timespec="minutes")
        was_in_agenda = meeting.get("in_agenda", False)

        if was_in_agenda:
            self.remove_from_agenda(meeting=meeting)

        meeting["start"] = new_start
        meeting["duration_minutes"] = duration_minutes
        self.save_meeting(meeting_id=meeting_id)

        if was_in_agenda:
            return self.add_to_agenda(meeting_id=meeting_id)

        return self.describe(meeting=meeting)


    def get_schedule(self, meeting_id):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        if not meeting.get("start"):
            raise ValueError("Cette réunion n'a pas encore de date : fixe-la d'abord.")

        return self.describe(meeting=meeting)


    def remove_from_agenda(self, meeting):

        self.agenda_source.delete_event(event_id=meeting["agenda_event_id"])
        meeting["in_agenda"] = False
        meeting.pop("agenda_event_id", None)


    def add_to_agenda(self, meeting_id):

        schedule = self.get_schedule(meeting_id=meeting_id)

        if schedule is None:
            return None

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting.get("in_agenda"):
            raise ValueError("Cette réunion est déjà dans l'agenda.")

        event = self.agenda_source.add_event(title=meeting["title"], start=schedule["start"], end=schedule["end"])
        meeting["in_agenda"] = True
        meeting["agenda_event_id"] = event["event_id"]
        self.save_meeting(meeting_id=meeting_id)

        return self.describe(meeting=meeting)