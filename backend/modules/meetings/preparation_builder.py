from datetime import datetime, timedelta

from modules.meetings.meeting_tool import MeetingTool


class PreparationBuilder(MeetingTool):
    """Construit la fiche de préparation d'une réunion, sans rien inventer (aucune IA).

    La fiche réunit seulement ce qui existe déjà : date, participants, ordre du jour,
    ce qui reste ouvert des réunions précédentes et les conflits d'agenda.
    """

    def __init__(self, meetings_service, conflict_detector):
        super().__init__(meetings_service=meetings_service)
        self.conflict_detector = conflict_detector

        self.max_previous_meetings = 3
        self.consent_labels = {True: "accord donné", False: "refus", None: "accord en attente"}


    def describe_date(self, meeting):

        if not meeting.get("start"):
            return "date pas encore fixée"

        start = datetime.fromisoformat(meeting["start"])
        end = start + timedelta(minutes=meeting["duration_minutes"])
        day_text = self.meetings_service.format_date(day=start.date())

        return f"{day_text}, de {start:%H:%M} à {end:%H:%M} ({meeting['duration_minutes']} min)"


    def find_previous_meetings(self, meeting):

        names = {participant["name"].lower() for participant in meeting["participants"]}
        previous = []

        for other in self.meetings_service.meetings.values():

            if other["meeting_id"] == meeting["meeting_id"] or other.get("report") is None:
                continue

            other_names = {participant["name"].lower() for participant in other["participants"]}

            if names & other_names and other["created_at"] <= meeting["created_at"]:
                previous.append(other)

        previous.sort(key=lambda other: other["created_at"], reverse=True)

        return previous[:self.max_previous_meetings]


    def build_previous_lines(self, meeting):

        lines = []

        for other in self.find_previous_meetings(meeting=meeting):
            report = other["report"]
            open_actions = [action for action in report["actions"] if action["status"] == "open"]

            if not report["open_points"] and not open_actions:
                continue

            lines.append(f"### {other['title']} ({other['created_at'][:10]})")

            for point in report["open_points"]:
                lines.append(f"- Point ouvert : {point}")

            for action in open_actions:
                due = f", pour le {action['due']}" if action["due"] else ""
                lines.append(f"- Action à faire : {action['who']} : {action['what']}{due}")

            lines.append("")

        return lines


    def find_conflicts(self, meeting):

        if not meeting.get("start"):
            return []

        start = datetime.fromisoformat(meeting["start"])
        end = start + timedelta(minutes=meeting["duration_minutes"])

        return self.conflict_detector.find_conflicts(
            start=start, end=end, ignore_meeting_id=meeting["meeting_id"]
        )


    def build(self, meeting_id):

        meeting = self.get_meeting(meeting_id=meeting_id)

        if meeting is None:
            return None

        conflicts = self.find_conflicts(meeting=meeting)

        lines = [f"# Fiche de préparation : {meeting['title']}", "", f"**Date** : {self.describe_date(meeting=meeting)}", ""]

        if conflicts:
            lines.append("## Attention, conflit d'agenda")
            for conflict in conflicts:
                lines.append(f"- {conflict['title']} ({conflict['start'][11:]} à {conflict['end'][11:]})")
            lines.append("")

        lines.append("## Participants")
        for participant in meeting["participants"]:
            lines.append(f"- {participant['name']} ({self.consent_labels[participant['consent']]})")
        if not meeting["participants"]:
            lines.append("- Aucun participant indiqué.")
        lines.append("")

        lines.append("## Ordre du jour")
        for number, point in enumerate(meeting["agenda"], start=1):
            lines.append(f"{number}. {point}")
        if not meeting["agenda"]:
            lines.append("Aucun point défini.")
        lines.append("")

        previous_lines = self.build_previous_lines(meeting=meeting)

        if previous_lines:
            lines.append("## À reprendre des réunions précédentes")
            lines.extend(previous_lines)

        return {"meeting_id": meeting_id, "text": "\n".join(lines).strip() + "\n", "conflicts": conflicts}