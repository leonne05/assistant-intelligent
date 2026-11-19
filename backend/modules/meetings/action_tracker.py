from datetime import date

from modules.meetings.meeting_tool import MeetingTool


class ActionTracker(MeetingTool):
    """Rassemble les actions de toutes les réunions dont le compte rendu est validé ou envoyé."""

    def __init__(self, meetings_service):
        super().__init__(meetings_service=meetings_service)
        self.followed_statuses = ["validated", "sent"]


    def describe_action(self, meeting, action, today):

        days_left = None

        if action["due"]:
            days_left = (date.fromisoformat(action["due"]) - today).days

        return {
            "meeting_id": meeting["meeting_id"],
            "meeting_title": meeting["title"],
            "action_id": action["id"],
            "who": action["who"],
            "what": action["what"],
            "due": action["due"],
            "status": action["status"],
            "days_left": days_left,
            "overdue": action["status"] == "open" and days_left is not None and days_left < 0,
        }


    def sort_key(self, action):
        return (action["due"] is None, action["due"] or "", action["meeting_title"])


    def collect(self, who=None, status="open", today=None):

        today = today or date.today()
        actions = []

        for meeting in self.meetings_service.meetings.values():
            report = meeting.get("report")

            if report is None or report["status"] not in self.followed_statuses:
                continue

            for action in report["actions"]:
                if status != "all" and action["status"] != status:
                    continue

                if who and action["who"].lower() != who.strip().lower():
                    continue

                actions.append(self.describe_action(meeting=meeting, action=action, today=today))

        return sorted(actions, key=self.sort_key)


    def count(self, today=None):

        open_actions = self.collect(status="open", today=today)

        return {
            "open": len(open_actions),
            "overdue": len([action for action in open_actions if action["overdue"]]),
            "done": len(self.collect(status="done", today=today)),
        }